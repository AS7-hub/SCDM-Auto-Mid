import pandas as pd
from typing import List, Tuple, Dict
from scdm.domain.schemas import Company, SupplyChainRelationship
from scdm.domain.constants import RelationshipType, DataLayer
from pydantic import ValidationError

def normalize_companies(dfs_with_metadata: List[Tuple[pd.DataFrame, Dict]]) -> Tuple[List[Company], List[Company]]:
    """
    Extracts canonical companies and focal companies from the raw parsed dataframes.
    Returns (canonical_companies, focal_companies).
    Duplicate company names with different IDs remain distinct.
    Exact ID duplicates are merged by keeping the first non-null values.
    """
    all_companies = {}
    focal_companies = {}

    for df, meta in dfs_with_metadata:
        # 1. Process focal company from metadata
        focal_id = meta.get("source_company_id")
        focal_name = meta.get("source_company_name")
        
        if focal_id and focal_id not in focal_companies:
            try:
                focal = Company(
                    company_id=str(focal_id),
                    company_name=str(focal_name) if focal_name else None,
                    is_focal=True
                )
                focal_companies[focal_id] = focal
                if focal_id not in all_companies:
                    all_companies[focal_id] = focal
            except ValidationError:
                pass
        
        # 2. Process counterparties from dataframe
        if "company_id" not in df.columns:
            continue
            
        for _, row in df.iterrows():
            cid = str(row["company_id"]).strip()
            # Clean floating point parsed as string like '4295869227.0' -> '4295869227'
            if cid.endswith(".0"):
                cid = cid[:-2]
            
            if not cid or cid.lower() == 'nan':
                continue
                
            cname = str(row["company_name"]).strip() if "company_name" in row and pd.notnull(row["company_name"]) else None
            ctype = str(row["company_type"]).strip() if "company_type" in row and pd.notnull(row["company_type"]) else None
            cregion = str(row["country_region"]).strip() if "country_region" in row and pd.notnull(row["country_region"]) else None
            cindustry = str(row["industry"]).strip() if "industry" in row and pd.notnull(row["industry"]) else None
            
            if cid not in all_companies:
                try:
                    all_companies[cid] = Company(
                        company_id=cid,
                        company_name=cname,
                        company_type=ctype,
                        country_region=cregion,
                        industry=cindustry,
                        is_focal=False
                    )
                except ValidationError:
                    continue
            else:
                # Merge logic: if we already have it, fill in missing values
                existing = all_companies[cid]
                if existing.company_name is None and cname: existing.company_name = cname
                if existing.company_type is None and ctype: existing.company_type = ctype
                if existing.country_region is None and cregion: existing.country_region = cregion
                if existing.industry is None and cindustry: existing.industry = cindustry

    return list(all_companies.values()), list(focal_companies.values())

def normalize_relationships(dfs_with_metadata: List[Tuple[pd.DataFrame, Dict]]) -> Tuple[List[SupplyChainRelationship], List[Dict]]:
    """
    Normalizes relationships into SUPPLIES and SELLS_TO.
    Returns (canonical_relationships, rejected_records).
    """
    relationships = []
    rejected = []
    
    # We use a set to track exact duplicates for provenance
    seen = set()
    
    for df, meta in dfs_with_metadata:
        focal_id = meta.get("source_company_id")
        focal_name = meta.get("source_company_name")
        source_file = meta.get("source_file")
        
        if not focal_id or "company_id" not in df.columns or "relationship" not in df.columns:
            continue
            
        focal_id = str(focal_id)
        if focal_id.endswith(".0"):
            focal_id = focal_id[:-2]
            
        for idx, row in df.iterrows():
            cid = str(row["company_id"]).strip()
            if cid.endswith(".0"): cid = cid[:-2]
                
            if not cid or cid.lower() == 'nan':
                rejected.append({"row": idx, "file": source_file, "reason": "Missing company_id"})
                continue
                
            rel_str = str(row["relationship"]).strip().lower()
            
            # Identify direction
            rel_type = None
            start_id = None
            end_id = None
            
            if rel_str == "supplier":
                rel_type = RelationshipType.SUPPLIES
                start_id = cid
                end_id = focal_id
            elif rel_str == "customer":
                rel_type = RelationshipType.SELLS_TO
                start_id = focal_id
                end_id = cid
            else:
                rejected.append({"row": idx, "file": source_file, "reason": f"Unsupported relationship: {rel_str}"})
                continue
                
            # Normalize confidence (assuming raw is a 0-1 scale or 0-100)
            conf = row.get("confidence_pct")
            if pd.notnull(conf):
                try:
                    conf_float = float(conf)
                    if conf_float <= 1.0:
                        conf_float = conf_float * 100.0  # convert 0.99 to 99.0
                    conf = conf_float
                except ValueError:
                    conf = None
            else:
                conf = None
                
            freshness = str(row.get("freshness")) if pd.notnull(row.get("freshness")) else None
            last_update = str(row.get("last_update_date")) if pd.notnull(row.get("last_update_date")) else None
            snippet_count = int(row.get("snippet_count")) if pd.notnull(row.get("snippet_count")) else None
            
            # Dedup hash: same endpoints, same type, same source company
            rel_hash = (rel_type, start_id, end_id, focal_id)
            if rel_hash in seen:
                # We could log this as a semantic duplicate, but for canonical we preserve one per focal observation
                continue
            else:
                seen.add(rel_hash)
                
            try:
                rel = SupplyChainRelationship(
                    relationship_type=rel_type,
                    start_id=start_id,
                    end_id=end_id,
                    source_company_id=focal_id,
                    source_company_name=focal_name,
                    confidence=conf,
                    freshness=freshness,
                    last_update_date=last_update,
                    snippet_count=snippet_count,
                    source_file=source_file
                )
                relationships.append(rel)
            except ValidationError as e:
                rejected.append({"row": idx, "file": source_file, "reason": f"Validation Error: {str(e)}"})
                
    return relationships, rejected
