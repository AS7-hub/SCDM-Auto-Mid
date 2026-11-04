import logging
from typing import Optional, List, Dict, Any, Set
from collections import defaultdict
from neo4j import GraphDatabase
from scdm.domain.schemas import ExposureResult, SupplierPath, ExposureStatus
from scdm.domain.constants import RelationshipType

logger = logging.getLogger(__name__)

class GraphTraversal:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_upstream_exposure(self, focal_company_id: str, max_depth: int = 3) -> ExposureResult:
        """
        Deterministically traces upstream supply chains to the given depth.
        Direction: (Supplier)-[SUPPLIES|SELLS_TO]->(Customer)...->(Focal)
        Returns structured topology avoiding structural duplication.
        """
        if max_depth < 1:
            raise ValueError("max_depth must be at least 1")
            
        query = f"""
        MATCH p = (supplier:Company)-[:SUPPLIES|SELLS_TO*1..{max_depth}]->(focal:Company {{company_id: $focal_id}})
        WITH p, supplier, nodes(p) AS path_nodes, relationships(p) AS path_rels, length(p) AS distance
        RETURN 
            [n IN path_nodes | n.company_id] AS ordered_ids,
            [r IN path_rels | type(r)] AS rel_types,
            distance
        ORDER BY distance ASC, supplier.company_id ASC
        """
        
        paths: List[SupplierPath] = []
        tier_groups: Dict[int, Set[str]] = defaultdict(set)
        max_observed = 0
        
        # Deduplication tracker for exact topological sequences
        seen_topology = set()

        with self.driver.session() as session:
            # First, check if focal company exists
            focal_res = session.run("MATCH (c:Company {company_id: $id}) RETURN c.company_id", id=focal_company_id)
            if not focal_res.single():
                return ExposureResult(
                    focal_company_id=focal_company_id,
                    status=ExposureStatus.UNRESOLVED
                )
                
            # Then trace paths
            res = session.run(query, focal_id=focal_company_id)
            
            for record in res:
                ordered_ids = record["ordered_ids"]
                rel_types_str = record["rel_types"]
                distance = record["distance"]
                
                # Deduplicate by node sequence
                top_key = tuple(ordered_ids)
                if top_key in seen_topology:
                    continue
                seen_topology.add(top_key)
                
                supplier_id = ordered_ids[0]
                tier_groups[distance].add(supplier_id)
                max_observed = max(max_observed, distance)
                
                # Map relationship strings to Enum
                rels_enum = []
                for rt in rel_types_str:
                    if "SUPPLIES" in rt:
                        rels_enum.append(RelationshipType.SUPPLIES)
                    else:
                        rels_enum.append(RelationshipType.SELLS_TO)
                        
                sp = SupplierPath(
                    focal_company_id=focal_company_id,
                    ordered_path=ordered_ids,
                    relationships=rels_enum,
                    distance=distance
                )
                paths.append(sp)
                
        if not paths:
            return ExposureResult(
                focal_company_id=focal_company_id,
                status=ExposureStatus.NO_GRAPH_EXPOSURE,
                paths=[],
                tier_groups={},
                max_depth_observed=0,
                path_count=0
            )
            
        # Convert set to list for pydantic serialization
        formatted_groups = {k: list(v) for k, v in tier_groups.items()}
        
        return ExposureResult(
            focal_company_id=focal_company_id,
            status=ExposureStatus.RESOLVED,
            paths=paths,
            tier_groups=formatted_groups,
            max_depth_observed=max_observed,
            path_count=len(paths)
        )

    def check_supplier_connectivity(self, supplier_id: str, focal_company_id: str) -> dict:
        """
        Deterministically checks if a candidate supplier is connected to the focal company,
        and returns global downstream supply metrics.
        """
        # Query 1: Global downstream out-degree (how many distinct companies do they supply?)
        out_degree_query = """
        MATCH (s:Company {company_id: $sup_id})-[:SUPPLIES|SELLS_TO]->(c:Company)
        RETURN count(DISTINCT c) AS out_degree
        """
        
        # Query 2: Shortest path to focal company (up to distance 4)
        path_query = """
        MATCH p = shortestPath((s:Company {company_id: $sup_id})-[:SUPPLIES|SELLS_TO*1..4]->(f:Company {company_id: $focal_id}))
        RETURN length(p) AS min_dist
        """
        
        result = {
            "is_connected_to_focal": False,
            "min_distance_to_focal": -1,
            "total_downstream_customers": 0
        }
        
        with self.driver.session() as session:
            # Check global out degree
            deg_res = session.run(out_degree_query, sup_id=supplier_id)
            deg_record = deg_res.single()
            if deg_record:
                result["total_downstream_customers"] = deg_record["out_degree"]
                
            # Check focal connectivity
            path_res = session.run(path_query, sup_id=supplier_id, focal_id=focal_company_id)
            path_record = path_res.single()
            if path_record and path_record.get("min_dist") is not None:
                result["is_connected_to_focal"] = True
                result["min_distance_to_focal"] = path_record["min_dist"]
                
        return result
