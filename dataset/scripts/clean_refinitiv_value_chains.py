import os
import glob
import pandas as pd
import numpy as np
import datetime
from pathlib import Path

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_DIR = PROJECT_ROOT / 'input'
BACKUP_INPUT_DIR = PROJECT_ROOT / 'datasets btp1'
CLEANED_DIR = PROJECT_ROOT / 'cleaned'
INDIVIDUAL_DIR = CLEANED_DIR / 'individual'
GRAPH_DIR = CLEANED_DIR / 'graph_ready'
REPORTS_DIR = CLEANED_DIR / 'reports'

COLUMN_MAPPING = {
    'Identifier': 'counterparty_id',
    'Company Name': 'counterparty_name',
    'Type': 'counterparty_type',
    'Relationship': 'relationship',
    'Country/Region': 'country_region',
    'Industry': 'industry',
    'Confidence Score (%)': 'confidence_pct',
    'Last Update Date': 'last_update_date',
    'Days Since Last Update': 'days_since_last_update',
    'Freshness': 'freshness',
    'Snippet Count': 'snippet_count',
    'Revenue (USD)': 'revenue_usd'
}

def to_snake_case(val):
    if not isinstance(val, str):
        return val
    return val.strip().lower().replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')

def setup_directories():
    for d in [INDIVIDUAL_DIR, GRAPH_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def read_refinitiv_file(filepath):
    try:
        df = pd.read_excel(filepath, header=None)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None, None
        
    focal_company_name = None
    focal_company_id = None
    export_timestamp = None
    header_idx = -1
    
    # scan for metadata and header
    for i, row in df.iterrows():
        # Metadata logic
        col0 = str(row[0]).strip() if pd.notna(row[0]) else ""
        col1 = row[1] if pd.notna(row[1]) else None
        
        if col0 == "Company Name" and col1 is not None:
            focal_company_name = str(col1).strip()
        elif col0 == "Company Id" and col1 is not None:
            focal_company_id = str(col1).strip().replace('.0', '')
        elif col0 == "Value Chains" and col1 is not None:
            export_timestamp = col1
            
        # Header logic
        row_strs = [str(x).strip() for x in row if pd.notna(x)]
        if "Identifier" in row_strs and "Company Name" in row_strs and "Relationship" in row_strs:
            header_idx = i
            break
            
    if header_idx == -1:
        print(f"Could not find valid header in {filepath.name}")
        return None, None
        
    if not focal_company_id:
        print(f"Warning: No Company Id found in {filepath.name} metadata")
        
    metadata = {
        'focal_company_name': focal_company_name,
        'focal_company_id': focal_company_id,
        'export_timestamp': export_timestamp,
        'source_filename': filepath.name,
        'row_count': len(df) - header_idx - 1,
        'filepath': filepath
    }
    
    # Get actual data
    df_data = pd.read_excel(filepath, skiprows=header_idx + 1)
    df_headers = pd.read_excel(filepath, skiprows=header_idx, nrows=0)
    df_data.columns = df_headers.columns
    
    return df_data, metadata

def clean_data(df, metadata):
    # Standardize column names
    new_cols = []
    for col in df.columns:
        col_str = str(col).strip()
        if col_str in COLUMN_MAPPING:
            new_cols.append(COLUMN_MAPPING[col_str])
        else:
            new_cols.append(to_snake_case(col_str))
    df.columns = new_cols
    
    # Required columns
    required_cols = ['counterparty_id', 'counterparty_name', 'relationship']
    for req in required_cols:
        if req not in df.columns:
            print(f"Missing required column {req} in {metadata['source_filename']}")
            return None
            
    # String cleaning
    str_cols = df.select_dtypes(include=['object']).columns
    for c in str_cols:
        df[c] = df[c].apply(lambda x: str(x).strip() if pd.notna(x) else np.nan)
        df[c] = df[c].replace('', np.nan)
        
    # ID handling
    df['counterparty_id'] = df['counterparty_id'].apply(lambda x: str(x).replace('.0', '') if pd.notna(x) else np.nan)
    
    df['source_company_id'] = metadata['focal_company_id']
    df['source_company_name'] = metadata['focal_company_name']
    df['source_tier'] = 1
    df['source_filename'] = metadata['source_filename']
    df['export_timestamp'] = metadata['export_timestamp']
    
    # Confidence Score
    if 'confidence_pct' in df.columns:
        df['confidence_pct'] = pd.to_numeric(df['confidence_pct'], errors='coerce')
        df['confidence_decimal'] = df['confidence_pct']
        
        # detect if 0-1 scale
        if df['confidence_pct'].max() <= 1.0:
            df['confidence_pct'] = df['confidence_pct'] * 100
        else:
            df['confidence_decimal'] = df['confidence_decimal'] / 100.0
            
    # Dates
    if 'last_update_date' in df.columns:
        df['last_update_date'] = pd.to_datetime(df['last_update_date'], errors='coerce').dt.strftime('%Y-%m-%d')
        
    # Numerics
    num_cols = ['days_since_last_update', 'freshness', 'snippet_count', 'revenue_usd']
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
            
    # Fill missing optional columns with NaN to avoid KeyError later
    for c in ['confidence_pct', 'confidence_decimal', 'last_update_date', 'days_since_last_update', 'freshness', 'snippet_count', 'revenue_usd', 'country_region', 'industry', 'counterparty_type']:
        if c not in df.columns:
            df[c] = np.nan
            
    return df

def main():
    setup_directories()
    input_path = INPUT_DIR if INPUT_DIR.exists() and any(INPUT_DIR.iterdir()) else BACKUP_INPUT_DIR
    
    if not input_path.exists():
        print(f"Input directory not found: {input_path}")
        return
        
    files = list(input_path.glob("*.xls*"))
    print(f"Found {len(files)} files in {input_path}")
    
    metadata_list = []
    df_dict = {}
    
    for f in files:
        df_raw, meta = read_refinitiv_file(f)
        if df_raw is not None and meta is not None:
            metadata_list.append(meta)
            df_dict[f.name] = (df_raw, meta)
            
    # Handle duplicates
    metadata_df = pd.DataFrame(metadata_list)
    canonical_files = []
    duplicate_files = []
    
    for focal_id, group in metadata_df.groupby('focal_company_id'):
        if len(group) == 1:
            canonical_files.append(group.iloc[0]['source_filename'])
        else:
            sorted_group = group.sort_values(by=['export_timestamp', 'row_count'], ascending=[False, False])
            canonical = sorted_group.iloc[0]['source_filename']
            canonical_files.append(canonical)
            dups = sorted_group.iloc[1:]['source_filename'].tolist()
            duplicate_files.extend(dups)
            
    if duplicate_files:
        dup_df = metadata_df[metadata_df['source_filename'].isin(duplicate_files)]
        dup_df.to_csv(REPORTS_DIR / 'duplicate_report.csv', index=False)
        
    print(f"Files successfully processed: {len(canonical_files) + len(duplicate_files)}")
    print(f"Duplicate/possible duplicate files: {len(duplicate_files)}")
    print(f"Files failed: {len(files) - len(metadata_list)}")
    
    all_cleaned_dfs = []
    
    # Process files
    for fname, (df_raw, meta) in df_dict.items():
        cleaned = clean_data(df_raw, meta)
        if cleaned is not None:
            # save individual file
            out_name = f"{meta['focal_company_name'].replace(' ', '_').replace(',', '').replace('.', '').replace('/', '_')}_clean.csv"
            
            # create duplicates folder if needed
            if fname in duplicate_files:
                dup_dir = INDIVIDUAL_DIR / 'duplicates'
                dup_dir.mkdir(exist_ok=True)
                cleaned.to_csv(dup_dir / out_name, index=False)
            else:
                cleaned.to_csv(INDIVIDUAL_DIR / out_name, index=False)
                all_cleaned_dfs.append(cleaned)
                
    if not all_cleaned_dfs:
        print("No valid data found.")
        return
        
    combined_df = pd.concat(all_cleaned_dfs, ignore_index=True)
    
    raw_rows = sum(m['row_count'] for m in metadata_list if m['source_filename'] in canonical_files)
    print(f"Total raw relationship rows: {raw_rows}")
    print(f"Total cleaned relationship rows: {len(combined_df)}")
    
    # Graph data preparation
    
    # Relationships
    rel_df = pd.DataFrame()
    
    supplies_mask = combined_df['relationship'].str.lower() == 'supplier'
    sells_to_mask = combined_df['relationship'].str.lower() == 'customer'
    
    # SUPPLIES: counterparty -> focal
    rel_supplies = combined_df[supplies_mask].copy()
    rel_supplies['start_id'] = rel_supplies['counterparty_id']
    rel_supplies['end_id'] = rel_supplies['source_company_id']
    rel_supplies['relationship'] = 'SUPPLIES'
    
    # SELLS TO: focal -> counterparty
    rel_sells = combined_df[sells_to_mask].copy()
    rel_sells['start_id'] = rel_sells['source_company_id']
    rel_sells['end_id'] = rel_sells['counterparty_id']
    rel_sells['relationship'] = 'SELLS_TO'
    
    graph_rels = pd.concat([rel_supplies, rel_sells], ignore_index=True)
    
    keep_cols = ['start_id', 'end_id', 'relationship', 'source_company_id', 'source_company_name', 
                 'source_tier', 'confidence_pct', 'confidence_decimal', 'last_update_date', 
                 'days_since_last_update', 'freshness', 'snippet_count', 'source_filename']
                 
    # Only keep cols that actually exist in combined_df
    final_keep_cols = [c for c in keep_cols if c in graph_rels.columns]
    graph_rels = graph_rels[final_keep_cols]
    
    graph_rels.to_csv(GRAPH_DIR / 'relationships.csv', index=False)
    
    rel_supplies[final_keep_cols].to_csv(GRAPH_DIR / 'relationships_supplies.csv', index=False)
    rel_sells[final_keep_cols].to_csv(GRAPH_DIR / 'relationships_sells_to.csv', index=False)
    
    print(f"SUPPLIES relationships: {len(rel_supplies)}")
    print(f"SELLS_TO relationships: {len(rel_sells)}")
    
    # Companies
    focal_companies = combined_df[['source_company_id', 'source_company_name']].drop_duplicates().copy()
    focal_companies.columns = ['company_id', 'company_name']
    
    counter_companies = combined_df[['counterparty_id', 'counterparty_name', 'counterparty_type', 
                                     'country_region', 'industry', 'revenue_usd']].drop_duplicates().copy()
    counter_companies.columns = ['company_id', 'company_name', 'company_type', 'country_region', 'industry', 'revenue_usd']
    
    companies = pd.concat([focal_companies, counter_companies], ignore_index=True)
    # Deduplicate, keep last valid entry to keep rich metadata from counterparty if available
    companies = companies.sort_values(by=['company_type', 'country_region']).drop_duplicates(subset=['company_id'], keep='first')
    
    companies.to_csv(GRAPH_DIR / 'companies.csv', index=False)
    print(f"Unique companies: {len(companies)}")
    print(f"Unique focal companies: {len(focal_companies)}")
    
    # Focal companies table
    focal_meta = combined_df[['source_company_id', 'source_company_name', 'source_filename', 'source_tier']].drop_duplicates()
    focal_meta.columns = ['company_id', 'company_name', 'source_filename', 'source_tier']
    focal_meta.to_csv(GRAPH_DIR / 'focal_companies.csv', index=False)
    
    # Data Quality Report
    dq = {
        'Missing IDs': combined_df['counterparty_id'].isna().sum(),
        'Invalid relationships': combined_df[~combined_df['relationship'].str.lower().isin(['supplier', 'customer'])].shape[0],
        'Duplicate relationships': graph_rels.duplicated(subset=['start_id', 'end_id', 'relationship']).sum(),
        'Self-loops': (graph_rels['start_id'] == graph_rels['end_id']).sum()
    }
    
    pd.DataFrame([dq]).to_csv(REPORTS_DIR / 'data_quality_report.csv', index=False)
    
    print(f"Missing IDs: {dq['Missing IDs']}")
    print(f"Invalid relationships: {dq['Invalid relationships']}")
    print(f"Duplicate relationships: {dq['Duplicate relationships']}")
    print(f"Self-loops: {dq['Self-loops']}")
    
    print("\nOutputs written to:")
    print(f"{CLEANED_DIR}")
    print("==================================================")
    
    # Write summary
    summary_data = {
        'Input files found': len(files),
        'Files successfully processed': len(canonical_files) + len(duplicate_files),
        'Duplicate/possible duplicate files': len(duplicate_files),
        'Files failed': len(files) - len(metadata_list),
        'Total raw relationship rows': raw_rows,
        'Total cleaned relationship rows': len(combined_df),
        'SUPPLIES relationships': len(rel_supplies),
        'SELLS_TO relationships': len(rel_sells),
        'Unique companies': len(companies),
        'Unique focal companies': len(focal_companies),
        'Missing IDs': dq['Missing IDs'],
        'Invalid relationships': dq['Invalid relationships'],
        'Duplicate relationships': dq['Duplicate relationships'],
        'Self-loops': dq['Self-loops']
    }
    
    pd.DataFrame([summary_data]).T.reset_index().to_csv(REPORTS_DIR / 'cleaning_summary.csv', index=False, header=['Metric', 'Value'])
    
if __name__ == '__main__':
    print("==================================================")
    print("REFINITIV VALUE CHAIN CLEANING")
    print("==================================================")
    main()
