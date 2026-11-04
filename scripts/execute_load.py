import logging
import os
from pathlib import Path
import pandas as pd
from scdm.core.config import config
from scdm.data.graph_loader import GraphLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def execute_load():
    base_dir = Path(__file__).resolve().parent.parent
    canonical_dir = base_dir / "output" / "canonical"
    if not canonical_dir.exists():
        canonical_dir = base_dir / "dataset" / "canonical"
    
    companies_file = canonical_dir / "canonical_companies.csv"
    rels_file = canonical_dir / "graph_ready_relationships.csv"
    
    logger.info("Loading CSV files...")
    df_companies = pd.read_csv(companies_file)
    df_rels = pd.read_csv(rels_file)
    
    # Initialize Loader using config credentials
    password = config.neo4j_password or "password"
    loader = GraphLoader(config.neo4j_uri, config.neo4j_username, password)
    
    try:
        # Run 1
        logger.info("--- RUN 1 (Initial Load) ---")
        loader.initialize_constraints()
        
        # We must load companies first so relationships can MERGE on them
        logger.info("Loading companies...")
        loader.load_companies(df_companies)
        
        # Verify endpoints before edges
        if loader.validate_endpoints_in_graph(df_rels):
            logger.info("Loading relationships...")
            loader.load_relationships(df_rels)
            
        logger.info("--- RUN 2 (Idempotency Test) ---")
        loader.load_companies(df_companies)
        loader.load_relationships(df_rels)
        
        # Run integrity checks internally from loader
        logger.info("--- PRE-FLIGHT VALIDATION (Internal) ---")
        loader.run_pre_flight_checks()
        
    finally:
        loader.close()
        
if __name__ == "__main__":
    execute_load()
