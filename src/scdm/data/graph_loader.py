import logging
import pandas as pd
from typing import List, Dict, Any
from neo4j import GraphDatabase
from scdm.core.config import config
from scdm.domain.constants import RelationshipType, DataLayer

logger = logging.getLogger(__name__)

class GraphLoader:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def initialize_constraints(self):
        """
        Creates constraints and indexes for safe idempotency.
        """
        with self.driver.session() as session:
            # Enforce unique company_id
            try:
                session.run("CREATE CONSTRAINT company_id_unique IF NOT EXISTS FOR (c:Company) REQUIRE c.company_id IS UNIQUE")
                logger.info("Constraint company_id_unique ensured.")
            except Exception as e:
                logger.warning(f"Could not create constraint: {e}")
                
            # Create index for faster endpoint lookups
            try:
                session.run("CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.company_name)")
                logger.info("Index company_name_idx ensured.")
            except Exception as e:
                logger.warning(f"Could not create index: {e}")

    def validate_endpoints_in_graph(self, canonical_edges: pd.DataFrame) -> bool:
        """
        Validates that the graph has the companies BEFORE we load edges.
        (Usually we load companies first, then edges).
        """
        if canonical_edges.empty:
            return True
            
        required_ids = set(canonical_edges['start_id'].astype(str)).union(set(canonical_edges['end_id'].astype(str)))
        
        with self.driver.session() as session:
            result = session.run("MATCH (c:Company) WHERE c.company_id IN $ids RETURN c.company_id as cid", ids=list(required_ids))
            found_ids = {str(record["cid"]) for record in result}
            
        missing = required_ids - found_ids
        if missing:
            logger.error(f"Cannot load edges: {len(missing)} required endpoints are missing in the graph.")
            return False
            
        return True

    def load_companies(self, df_companies: pd.DataFrame):
        """
        Idempotent MERGE for Company nodes.
        Uses company_id for stable identity.
        """
        query = """
        UNWIND $rows AS row
        MERGE (c:Company {company_id: row.company_id})
        SET c.company_name = row.company_name,
            c.company_type = row.company_type,
            c.country_region = row.country_region,
            c.industry = row.industry,
            c.is_focal = row.is_focal,
            c.layer = $layer
        """
        
        # Replace NaN/NaT with None for Neo4j compatibility
        df_clean = df_companies.where(pd.notnull(df_companies), None)
        # Ensure company_id is string
        df_clean['company_id'] = df_clean['company_id'].astype(str)
        
        rows = df_clean.to_dict('records')
        
        with self.driver.session() as session:
            result = session.run(query, rows=rows, layer=DataLayer.GRAPH_DATA.value)
            counters = result.consume().counters
            logger.info(f"Loaded companies: {counters.nodes_created} created, {counters.properties_set} properties set.")

    def load_relationships(self, df_rels: pd.DataFrame):
        """
        Idempotent MERGE for relationships.
        Direction is preserved exactly.
        """
        df_clean = df_rels.where(pd.notnull(df_rels), None)
        df_clean['start_id'] = df_clean['start_id'].astype(str)
        df_clean['end_id'] = df_clean['end_id'].astype(str)
        
        # Separate SUPPLIES and SELLS_TO
        supplies_rows = df_clean[df_clean['relationship_type'].astype(str).str.contains('SUPPLIES')].to_dict('records')
        sells_to_rows = df_clean[df_clean['relationship_type'].astype(str).str.contains('SELLS_TO')].to_dict('records')
        
        with self.driver.session() as session:
            # Load SUPPLIES
            if supplies_rows:
                query_supplies = """
                UNWIND $rows AS row
                MATCH (start:Company {company_id: row.start_id})
                MATCH (end:Company {company_id: row.end_id})
                MERGE (start)-[r:SUPPLIES]->(end)
                SET r.confidence = toFloat(row.confidence),
                    r.freshness = row.freshness,
                    r.last_update_date = row.last_update_date,
                    r.snippet_count = toInteger(row.snippet_count),
                    r.source_file = row.source_file,
                    r.source_company_id = row.source_company_id,
                    r.source_company_name = row.source_company_name,
                    r.layer = $layer
                """
                result = session.run(query_supplies, rows=supplies_rows, layer=DataLayer.GRAPH_DATA.value)
                counters = result.consume().counters
                logger.info(f"Loaded SUPPLIES: {counters.relationships_created} created, {counters.properties_set} properties set.")
                
            # Load SELLS_TO
            if sells_to_rows:
                query_sells = """
                UNWIND $rows AS row
                MATCH (start:Company {company_id: row.start_id})
                MATCH (end:Company {company_id: row.end_id})
                MERGE (start)-[r:SELLS_TO]->(end)
                SET r.confidence = toFloat(row.confidence),
                    r.freshness = row.freshness,
                    r.last_update_date = row.last_update_date,
                    r.snippet_count = toInteger(row.snippet_count),
                    r.source_file = row.source_file,
                    r.source_company_id = row.source_company_id,
                    r.source_company_name = row.source_company_name,
                    r.layer = $layer
                """
                result = session.run(query_sells, rows=sells_to_rows, layer=DataLayer.GRAPH_DATA.value)
                counters = result.consume().counters
                logger.info(f"Loaded SELLS_TO: {counters.relationships_created} created, {counters.properties_set} properties set.")

    def run_pre_flight_checks(self):
        """
        Runs validation checks on the graph integrity.
        Does NOT alter data.
        """
        with self.driver.session() as session:
            # Check for duplicate company_ids
            res = session.run("MATCH (c:Company) WITH c.company_id AS cid, count(c) as count WHERE count > 1 RETURN cid")
            duplicates = [r["cid"] for r in res]
            if duplicates:
                logger.warning(f"Found {len(duplicates)} duplicate company_ids in the graph. E.g. {duplicates[:3]}")
                
            # Check for unrelated labels
            res = session.run("MATCH (n) RETURN labels(n) as labels, count(n) as count")
            for record in res:
                labels = record["labels"]
                if "Company" not in labels:
                    logger.warning(f"Found unrelated label {labels}: {record['count']} nodes")
                    
            logger.info("Pre-flight checks completed.")
