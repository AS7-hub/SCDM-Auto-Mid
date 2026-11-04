import json
import os
from typing import List, Dict, Tuple
from scdm.domain.schemas import Company, SupplyChainRelationship
from scdm.domain.constants import RelationshipType

def validate_endpoints(
    relationships: List[SupplyChainRelationship],
    companies: List[Company]
) -> Tuple[List[SupplyChainRelationship], List[Dict]]:
    """
    Validates that relationship endpoints reference canonical companies.
    Returns (valid_relationships, orphan_errors).
    """
    valid_ids = {c.company_id for c in companies}
    valid_rels = []
    orphans = []
    
    for rel in relationships:
        if rel.start_id not in valid_ids or rel.end_id not in valid_ids:
            orphans.append({
                "relationship_type": rel.relationship_type.value,
                "start_id": rel.start_id,
                "end_id": rel.end_id,
                "source_file": rel.source_file,
                "reason": "Orphan endpoint"
            })
        else:
            valid_rels.append(rel)
            
    return valid_rels, orphans

def generate_validation_report(
    files_processed: List[str],
    companies: List[Company],
    relationships: List[SupplyChainRelationship],
    rejected_records: List[Dict],
    orphan_errors: List[Dict],
    output_dir: str
):
    """
    Generates a machine-readable validation report in the output directory.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    missing_names = sum(1 for c in companies if c.company_name is None)
    
    # Calculate duplicate names (distinct IDs, same name)
    name_counts = {}
    for c in companies:
        if c.company_name:
            name_counts[c.company_name] = name_counts.get(c.company_name, 0) + 1
    duplicate_names = sum(1 for v in name_counts.values() if v > 1)
    
    report = {
        "files_processed_count": len(files_processed),
        "files_processed": files_processed,
        "companies": {
            "total_canonical": len(companies),
            "missing_names": missing_names,
            "duplicate_names_count": duplicate_names
        },
        "relationships": {
            "total_canonical": len(relationships),
            "supplies_count": sum(1 for r in relationships if r.relationship_type == RelationshipType.SUPPLIES),
            "sells_to_count": sum(1 for r in relationships if r.relationship_type == RelationshipType.SELLS_TO),
        },
        "errors_and_warnings": {
            "rejected_rows_count": len(rejected_records),
            "rejected_records": rejected_records,
            "orphan_endpoints_count": len(orphan_errors),
            "orphan_endpoints": orphan_errors
        }
    }
    
    report_path = os.path.join(output_dir, "validation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)
        
    return report
