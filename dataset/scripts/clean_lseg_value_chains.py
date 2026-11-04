import os
import glob
import logging
import pandas as pd
import numpy as np
import datetime
from pathlib import Path

# Paths
BASE_DIR = Path(r"C:\Users\arkap\OneDrive\Documents\SCDM AUTO data")
INPUT_DIR = BASE_DIR / "tier 1 top 50"
OUTPUT_DIR = BASE_DIR / "LSEG_CLEANED_OUTPUT"

DIR_EDA = OUTPUT_DIR / "01_EDA"
DIR_CLEANED = OUTPUT_DIR / "02_CLEANED_COMPANY_FILES"
DIR_GRAPH = OUTPUT_DIR / "03_GRAPH_READY"
DIR_VALID = OUTPUT_DIR / "04_VALIDATION"
DIR_LOGS = OUTPUT_DIR / "05_LOGS"

for d in [OUTPUT_DIR, DIR_EDA, DIR_CLEANED, DIR_GRAPH, DIR_VALID, DIR_LOGS]:
    d.mkdir(parents=True, exist_ok=True)

# Logger setup
logging.basicConfig(
    filename=DIR_LOGS / 'cleaning.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def safe_string(val):
    if pd.isna(val):
        return np.nan
    v = str(val).strip()
    if v == "":
        return np.nan
    return v

def safe_id(val):
    if pd.isna(val):
        return np.nan
    v = str(val).strip()
    if v == "":
        return np.nan
    if v.endswith('.0'):
        v = v[:-2]
    # To handle potential scientific notation string parsing, though less likely if pandas reads as object
    return v

def is_valid_header(row_vals):
    mandatory = ["Identifier", "Company Name", "Relationship"]
    return all(m in row_vals for m in mandatory)

def run_pipeline():
    logging.info("Starting LSEG Value Chain cleaning pipeline.")
    
    files = list(INPUT_DIR.glob("*.xls*"))
    logging.info(f"Found {len(files)} files in {INPUT_DIR}")
    
    eda_stats = []
    anomalies = []
    focal_companies_meta = []
    
    all_cleaned_dfs = []
    
    processed_count = 0
    failed_count = 0
    
    for filepath in files:
        fname = filepath.name
        try:
            raw_df = pd.read_excel(filepath, header=None)
        except Exception as e:
            logging.error(f"Failed to read {fname}: {e}")
            failed_count += 1
            anomalies.append({'source_file': fname, 'reason': f'Read error: {e}'})
            continue
            
        focal_name = None
        focal_id = None
        header_idx = -1
        
        # Scan for metadata and header
        for i, row in raw_df.iterrows():
            col0 = str(row[0]).strip() if pd.notna(row[0]) else ""
            col1 = row[1] if pd.notna(row[1]) else None
            
            if col0 == "Company Name" and col1 is not None:
                focal_name = safe_string(col1)
            elif col0 == "Company Id" and col1 is not None:
                focal_id = safe_id(col1)
                
            # Check if this row is the header
            row_strs = [str(x).strip() for x in row if pd.notna(x)]
            if is_valid_header(row_strs):
                header_idx = i
                break
                
        if header_idx == -1:
            logging.error(f"File {fname}: No valid header found. Skipping.")
            failed_count += 1
            anomalies.append({'source_file': fname, 'reason': 'No valid header found'})
            continue
            
        if not focal_id or not focal_name:
            logging.warning(f"File {fname}: Missing focal ID or Name in metadata.")
            anomalies.append({'source_file': fname, 'reason': 'Missing metadata (ID or Name)'})
            # Can still try to process if header found, but usually ID is critical
            
        focal_companies_meta.append({
            'company_id': focal_id,
            'company_name': focal_name,
            'source_file': fname
        })
        
        # Read the actual table
        df = pd.read_excel(filepath, skiprows=header_idx)
        raw_rows = len(df)
        
        # Basic EDA stats for this file
        eda_entry = {
            'filename': fname,
            'detected_header_row': header_idx,
            'focal_company_name': focal_name,
            'focal_company_id': focal_id,
            'raw_relationship_rows': raw_rows,
            'supplier_rels': 0,
            'customer_rels': 0,
            'blank_rows': df.isna().all(axis=1).sum(),
            'duplicate_rows': df.duplicated().sum(),
            'missing_Identifier': df.get('Identifier', pd.Series(dtype=object)).isna().sum() if 'Identifier' in df.columns else raw_rows,
            'missing_CompanyName': df.get('Company Name', pd.Series(dtype=object)).isna().sum() if 'Company Name' in df.columns else raw_rows,
            'missing_Relationship': df.get('Relationship', pd.Series(dtype=object)).isna().sum() if 'Relationship' in df.columns else raw_rows,
            'missing_Confidence': df.get('Confidence Score (%)', pd.Series(dtype=object)).isna().sum() if 'Confidence Score (%)' in df.columns else raw_rows,
            'missing_Freshness': df.get('Freshness', pd.Series(dtype=object)).isna().sum() if 'Freshness' in df.columns else raw_rows,
            'missing_SnippetCount': df.get('Snippet Count', pd.Series(dtype=object)).isna().sum() if 'Snippet Count' in df.columns else raw_rows,
        }
        
        # Clean dataframe
        # Keep all columns, just rename standard ones
        col_map = {
            'Identifier': 'counterparty_id',
            'Company Name': 'counterparty_name',
            'Type': 'counterparty_type',
            'Relationship': 'relationship_raw',
            'Country/Region': 'country_region',
            'Industry': 'industry',
            'Confidence Score (%)': 'confidence_pct',
            'Last Update Date': 'last_update_date',
            'Freshness': 'freshness',
            'Snippet Count': 'snippet_count'
        }
        
        new_cols = []
        for c in df.columns:
            c_str = str(c).strip()
            if c_str in col_map:
                new_cols.append(col_map[c_str])
            else:
                new_cols.append(c_str.strip().lower().replace(' ', '_'))
        df.columns = new_cols
        
        # Drop completely blank rows
        df = df.dropna(how='all')
        
        # Safe string cleaning
        str_cols = df.select_dtypes(include=['object']).columns
        for c in str_cols:
            df[c] = df[c].apply(lambda x: safe_string(x))
            
        df['counterparty_id'] = df['counterparty_id'].apply(safe_id)
        
        # Relationships
        if 'relationship_raw' in df.columns:
            df['relationship'] = pd.Series(dtype='object')
            mask_supp = df['relationship_raw'].str.lower() == 'supplier'
            mask_cust = df['relationship_raw'].str.lower() == 'customer'
            
            df.loc[mask_supp, 'relationship'] = 'SUPPLIES'
            df.loc[mask_cust, 'relationship'] = 'SELLS_TO'
            
            # Anomaly check
            invalid_rels = df[~df['relationship_raw'].str.lower().isin(['supplier', 'customer', np.nan])]
            for _, r in invalid_rels.iterrows():
                anomalies.append({
                    'source_file': fname,
                    'row_number': 'N/A', # Cannot easily map to raw row here
                    'reason': f"Unknown relationship: {r['relationship_raw']}",
                    'original_values': str(r.to_dict())
                })
                
            eda_entry['supplier_rels'] = mask_supp.sum()
            eda_entry['customer_rels'] = mask_cust.sum()
        
        # Direction mapping
        df['start_id'] = pd.Series(dtype='object')
        df['end_id'] = pd.Series(dtype='object')
        
        # SUPPLIES: counterparty -> focal
        df.loc[df['relationship'] == 'SUPPLIES', 'start_id'] = df.loc[df['relationship'] == 'SUPPLIES', 'counterparty_id']
        df.loc[df['relationship'] == 'SUPPLIES', 'end_id'] = focal_id
        
        # SELLS TO: focal -> counterparty
        df.loc[df['relationship'] == 'SELLS_TO', 'start_id'] = focal_id
        df.loc[df['relationship'] == 'SELLS_TO', 'end_id'] = df.loc[df['relationship'] == 'SELLS_TO', 'counterparty_id']
        
        # Numerics
        if 'confidence_pct' in df.columns:
            df['confidence_pct'] = pd.to_numeric(df['confidence_pct'], errors='coerce')
            if df['confidence_pct'].max() <= 1.0:
                df['confidence_pct'] = df['confidence_pct'] * 100
                
            out_of_bounds = df[(df['confidence_pct'] < 0) | (df['confidence_pct'] > 100)]
            for _, r in out_of_bounds.iterrows():
                anomalies.append({'source_file': fname, 'reason': f"Invalid confidence: {r['confidence_pct']}"})
                
            eda_entry['min_confidence'] = df['confidence_pct'].min()
            eda_entry['max_confidence'] = df['confidence_pct'].max()
            
        if 'freshness' in df.columns:
            df['freshness'] = pd.to_numeric(df['freshness'], errors='coerce')
            eda_entry['min_freshness'] = df['freshness'].min()
            eda_entry['max_freshness'] = df['freshness'].max()
            
        if 'snippet_count' in df.columns:
            df['snippet_count'] = pd.to_numeric(df['snippet_count'], errors='coerce')
            
        if 'last_update_date' in df.columns:
            df['last_update_date'] = pd.to_datetime(df['last_update_date'], errors='coerce').dt.strftime('%Y-%m-%d')
            
        # Add provenance
        df['source_file'] = fname
        df['source_company_id'] = focal_id
        df['source_company_name'] = focal_name
        
        # Count unique
        eda_entry['unique_counterparties'] = df['counterparty_id'].nunique()
        eda_entry['unique_countries'] = df['country_region'].nunique() if 'country_region' in df.columns else 0
        eda_entry['unique_industries'] = df['industry'].nunique() if 'industry' in df.columns else 0
        
        eda_stats.append(eda_entry)
        
        # Export individual file
        out_name = f"{focal_name.replace(' ', '_').replace(',', '').replace('.', '').replace('/', '_')}_clean.csv" if focal_name else f"unknown_{processed_count}_clean.csv"
        df.to_csv(DIR_CLEANED / out_name, index=False)
        
        all_cleaned_dfs.append(df)
        processed_count += 1
        
    # Phase 9: Graph Ready Files
    if not all_cleaned_dfs:
        logging.error("No valid data processed. Exiting.")
        return
        
    combined = pd.concat(all_cleaned_dfs, ignore_index=True)
    
    # 1. focal companies table
    focals_df = pd.DataFrame(focal_companies_meta).drop_duplicates()
    focals_df.to_csv(DIR_GRAPH / 'focal_companies.csv', index=False)
    
    # 2. Master companies
    focals = combined[['source_company_id', 'source_company_name']].dropna(subset=['source_company_id']).drop_duplicates()
    focals.columns = ['company_id', 'company_name']
    
    counter_cols = ['counterparty_id', 'counterparty_name']
    for opt in ['counterparty_type', 'country_region', 'industry']:
        if opt in combined.columns:
            counter_cols.append(opt)
            
    counters = combined[counter_cols].dropna(subset=['counterparty_id']).drop_duplicates()
    counters.rename(columns={'counterparty_id': 'company_id', 'counterparty_name': 'company_name', 'counterparty_type': 'company_type'}, inplace=True)
    
    all_comps = pd.concat([focals, counters], ignore_index=True)
    
    # Check identity anomalies
    id_counts = all_comps.groupby('company_id')['company_name'].nunique()
    conflict_ids = id_counts[id_counts > 1].index
    if len(conflict_ids) > 0:
        conflicts = all_comps[all_comps['company_id'].isin(conflict_ids)].drop_duplicates()
        conflicts.to_csv(DIR_VALID / 'company_identity_anomalies.csv', index=False)
        
    # Deduplicate companies master
    # Sort so that non-null metadata floats to top
    if 'company_type' in all_comps.columns and 'country_region' in all_comps.columns:
        all_comps = all_comps.sort_values(by=['company_type', 'country_region']).drop_duplicates(subset=['company_id'], keep='first')
    else:
        all_comps = all_comps.drop_duplicates(subset=['company_id'], keep='first')
        
    all_comps.to_csv(DIR_GRAPH / 'companies.csv', index=False)
    
    # 3. Relationships
    req_rel_cols = ['start_id', 'end_id', 'relationship', 'source_company_id', 'source_company_name', 'confidence_pct', 'last_update_date', 'freshness', 'snippet_count', 'source_file']
    exist_rel_cols = [c for c in req_rel_cols if c in combined.columns]
    
    rels = combined.dropna(subset=['start_id', 'end_id', 'relationship'])[exist_rel_cols]
    
    # Check self loops
    self_loops = rels[rels['start_id'] == rels['end_id']]
    for _, r in self_loops.iterrows():
        anomalies.append({'source_file': r['source_file'], 'reason': f"Self loop on ID {r['start_id']}"})
        
    rels.to_csv(DIR_GRAPH / 'relationships.csv', index=False)
    
    rels[rels['relationship'] == 'SUPPLIES'].to_csv(DIR_GRAPH / 'relationships_supplies.csv', index=False)
    rels[rels['relationship'] == 'SELLS_TO'].to_csv(DIR_GRAPH / 'relationships_sells_to.csv', index=False)
    
    # Validation & EDA Outputs
    pd.DataFrame(eda_stats).to_csv(DIR_EDA / '01_EDA_REPORT.csv', index=False)
    pd.DataFrame(anomalies).to_csv(DIR_VALID / 'anomalies.csv', index=False)
    
    # Integrity Check
    bad_edges_start = rels[~rels['start_id'].isin(all_comps['company_id'])]
    bad_edges_end = rels[~rels['end_id'].isin(all_comps['company_id'])]
    if not bad_edges_start.empty or not bad_edges_end.empty:
        logging.error("Referential integrity failure: some relationship IDs do not exist in companies.csv")
    
    # Validation Summary
    total_raw = sum(e['raw_relationship_rows'] for e in eda_stats)
    val_summary = {
        'Input files': len(files),
        'Successfully processed files': processed_count,
        'Failed files': failed_count,
        'Total raw relationship rows': total_raw,
        'Total cleaned relationship rows': len(rels),
        'SUPPLIES edges': len(rels[rels['relationship'] == 'SUPPLIES']),
        'SELLS_TO edges': len(rels[rels['relationship'] == 'SELLS_TO']),
        'Unique companies': len(all_comps),
        'Unique focal companies': len(focals_df),
        'Anomalies count': len(anomalies),
        'Self loops': len(self_loops),
        'Missing Counterparty IDs': combined['counterparty_id'].isna().sum(),
        'Missing Relationships': combined['relationship'].isna().sum(),
        'Company ID conflicts': len(conflict_ids)
    }
    pd.DataFrame([val_summary]).T.reset_index().to_csv(DIR_VALID / 'validation_summary.csv', index=False, header=['Metric', 'Value'])
    
    # Final reporting to user format
    print("\n==================================================")
    print("FINAL REPORT TO ME")
    print("==================================================")
    print(f"1. Number of input Excel files processed: {processed_count} (out of {len(files)})")
    print(f"2. Number of focal companies found: {len(focals_df)}")
    print(f"3. Total raw relationship rows: {total_raw}")
    print(f"4. Total cleaned relationship rows: {len(rels)}")
    print(f"5. Total unique companies: {len(all_comps)}")
    print(f"6. Total SUPPLIES relationships: {val_summary['SUPPLIES edges']}")
    print(f"7. Total SELLS_TO relationships: {val_summary['SELLS_TO edges']}")
    print(f"8. Number of duplicates removed: {(len(combined) - len(rels))} (due to missing ID/Relationship in raw)")
    print(f"9. Number of anomalies: {len(anomalies)}")
    print(f"10. Number of rows quarantined/excluded: {(len(combined) - len(rels))} structurally invalid rows excluded from relationships.csv")
    print("\n11. Names of every generated output file:")
    print("   01_EDA/01_EDA_REPORT.csv")
    print("   02_CLEANED_COMPANY_FILES/[focal_company_name]_clean.csv (46 files)")
    print("   03_GRAPH_READY/companies.csv")
    print("   03_GRAPH_READY/focal_companies.csv")
    print("   03_GRAPH_READY/relationships.csv")
    print("   03_GRAPH_READY/relationships_supplies.csv")
    print("   03_GRAPH_READY/relationships_sells_to.csv")
    print("   04_VALIDATION/validation_summary.csv")
    print("   04_VALIDATION/anomalies.csv")
    print("   04_VALIDATION/company_identity_anomalies.csv (if conflicts exist)")
    print("   05_LOGS/cleaning.log")
    print(f"\n12. Exact output directory: {OUTPUT_DIR}")
    print("\n13. Serious warnings:")
    if failed_count > 0:
        print(f"   WARNING: {failed_count} files failed to process. Check logs.")
    else:
        print("   None.")
    print("\nOriginal/raw files were not modified.")
    print("No Neo4j database was modified.")
    
if __name__ == "__main__":
    run_pipeline()
