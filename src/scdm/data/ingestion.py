import os
import pandas as pd
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

def find_header_and_metadata(filepath: str) -> Tuple[int, Dict[str, str]]:
    """
    Scans the first 15 rows to detect the true tabular header row
    and extracts focal company metadata (id, name).
    Returns (header_row_index, metadata_dict)
    """
    # Use header=None so we get all rows including row 0
    df = pd.read_excel(filepath, nrows=15, header=None)
    
    metadata = {
        "source_company_id": None,
        "source_company_name": None,
        "source_file": os.path.basename(filepath)
    }
    
    header_idx = 0
    
    for i, row in df.iterrows():
        # Clean row values to safely compare
        row_values = [str(x).strip() for x in row.values if pd.notnull(x)]
        
        # Only assign metadata if not already found (prevents header row from overwriting)
        if "Company Id" in row_values and metadata["source_company_id"] is None:
            idx = [str(x).strip() for x in row.values].index("Company Id")
            if idx + 1 < len(row.values) and pd.notnull(row.values[idx+1]):
                val = row.values[idx+1]
                metadata["source_company_id"] = str(int(float(val))) if isinstance(val, (int, float)) else str(val).strip()
        
        if "Company Name" in row_values and metadata["source_company_name"] is None:
            idx = [str(x).strip() for x in row.values].index("Company Name")
            if idx + 1 < len(row.values) and pd.notnull(row.values[idx+1]):
                metadata["source_company_name"] = str(row.values[idx+1]).strip()
        
        # Detect header row
        if "Identifier" in row_values and "Relationship" in row_values:
            header_idx = i
            break
            
    return header_idx, metadata

def load_raw_file(filepath: str) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Loads the raw excel file, starting from the detected header.
    Returns the dataframe and the extracted source metadata.
    """
    header_idx, metadata = find_header_and_metadata(filepath)
    
    df = pd.read_excel(filepath, header=header_idx)
    
    # Strip whitespace from columns before renaming
    df.columns = [str(c).strip() for c in df.columns]
    
    # Normalize column names to snake_case equivalent
    col_mapping = {
        "Identifier": "company_id",
        "Company Name": "company_name",
        "Type": "company_type",
        "Relationship": "relationship",
        "Country/Region": "country_region",
        "Industry": "industry",
        "Confidence Score (%)": "confidence_pct",
        "Last Update Date": "last_update_date",
        "Days Since Last Update": "days_since_update",
        "Freshness": "freshness",
        "Snippet Count": "snippet_count"
    }
    
    df = df.rename(columns=col_mapping)
    
    # Filter only relevant columns if they exist
    cols_to_keep = [c for c in col_mapping.values() if c in df.columns]
    df = df[cols_to_keep]
    
    return df, metadata

def process_raw_directory(directory: str) -> list[Tuple[pd.DataFrame, Dict[str, str]]]:
    """
    Iterates through all .xlsx files in the directory and parses them.
    Returns a list of (DataFrame, metadata) tuples.
    """
    results = []
    if not os.path.exists(directory):
        logger.warning(f"Directory not found: {directory}")
        return results
        
    for filename in os.listdir(directory):
        if filename.endswith(".xlsx") and not filename.startswith("~"):
            filepath = os.path.join(directory, filename)
            try:
                df, metadata = load_raw_file(filepath)
                results.append((df, metadata))
            except Exception as e:
                logger.error(f"Failed to process {filename}: {e}")
                
    return results
