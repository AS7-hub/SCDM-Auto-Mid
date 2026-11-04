import os
import json
import pandas as pd
from scdm.data.ingestion import process_raw_directory
from scdm.data.normalization import normalize_companies, normalize_relationships
from scdm.data.validation import validate_endpoints, generate_validation_report
import logging

logger = logging.getLogger(__name__)

def run_pipeline(raw_data_dir: str, output_dir: str):
    logger.info(f"Starting ingestion pipeline from {raw_data_dir}")
    
    # 1. Ingest raw files
    dfs_with_metadata = process_raw_directory(raw_data_dir)
    files_processed = [meta["source_file"] for _, meta in dfs_with_metadata]
    logger.info(f"Processed {len(files_processed)} files")
    
    # 2. Normalize
    canonical_companies, focal_companies = normalize_companies(dfs_with_metadata)
    relationships, rejected = normalize_relationships(dfs_with_metadata)
    
    # 3. Validate
    valid_relationships, orphans = validate_endpoints(relationships, canonical_companies)
    
    # 4. Generate report
    report = generate_validation_report(
        files_processed=files_processed,
        companies=canonical_companies,
        relationships=relationships,  # reporting before orphan filter so orphans are visible
        rejected_records=rejected,
        orphan_errors=orphans,
        output_dir=output_dir
    )
    
    # 5. Output Canonical/Graph-Ready CSVs
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    comp_dicts = [c.model_dump() for c in canonical_companies]
    pd.DataFrame(comp_dicts).to_csv(os.path.join(output_dir, "canonical_companies.csv"), index=False)
    
    rel_dicts = [r.model_dump() for r in valid_relationships]
    pd.DataFrame(rel_dicts).to_csv(os.path.join(output_dir, "graph_ready_relationships.csv"), index=False)
    
    focal_dicts = [f.model_dump() for f in focal_companies]
    pd.DataFrame(focal_dicts).to_csv(os.path.join(output_dir, "focal_companies.csv"), index=False)
    
    logger.info("Pipeline complete.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from scdm.core.config import config
    
    # We enforce using 'tier 1 top 50' based on our explicit plan decision
    primary_raw_dir = r"C:\Users\arkap\OneDrive\Documents\SCDM AUTO data\tier 1 top 50"
    out_dir = r"C:\Users\arkap\OneDrive\Documents\SCDM Auto Mid\output\canonical"
    
    run_pipeline(primary_raw_dir, out_dir)
