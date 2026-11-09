#!/usr/bin/env python3
"""
Generate Master Company & Unique Code Dictionary Sheet
-----------------------------------------------------
Extracts all unique company codes and listed company names from the canonical dataset,
sorts them in strict alphabetical order (A-Z), and exports the master sheet.
"""

from pathlib import Path
import pandas as pd

def generate_dictionary():
    base_dir = Path(__file__).resolve().parent.parent
    input_file = base_dir / "output" / "canonical" / "canonical_companies.csv"
    if not input_file.exists():
        input_file = base_dir / "dataset" / "canonical" / "canonical_companies.csv"

    print(f"Reading dataset from: {input_file}")
    df = pd.read_csv(input_file)

    def format_clean_name(row):
        name = row['company_name']
        cid = str(row['company_id'])
        country = str(row['country_region']) if pd.notna(row['country_region']) else 'Unspecified'
        if pd.isna(name) or not str(name).strip() or str(name).lower() == 'nan':
            return f"Private Entity ({cid}, {country})"
        return str(name).strip()

    df['clean_company_name'] = df.apply(format_clean_name, axis=1)
    df['sort_key'] = df['clean_company_name'].str.lower()
    df_sorted = df.sort_values(by='sort_key').reset_index(drop=True)

    result_df = pd.DataFrame({
        'Company Name': df_sorted['clean_company_name'],
        'Unique Company Code': df_sorted['company_id'].astype(str),
        'Company Type': df_sorted['company_type'].fillna('Unspecified'),
        'Country / Region': df_sorted['country_region'].fillna('Not Specified'),
        'Industry Sector': df_sorted['industry'].replace('-', 'Not Specified').fillna('Not Specified'),
        'Is Focal OEM': df_sorted['is_focal'].apply(lambda x: 'Yes' if x else 'No')
    })

    # Destination paths
    destinations = [
        base_dir / "all_unique_companies_and_codes.csv",
        base_dir / "output" / "canonical" / "all_unique_companies_and_codes.csv",
        base_dir / "dataset" / "canonical" / "all_unique_companies_and_codes.csv"
    ]

    for dest in destinations:
        dest.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(dest, index=False, encoding='utf-8')
        print(f"✓ Saved sheet ({len(result_df)} rows) to: {dest}")

    return result_df

if __name__ == "__main__":
    generate_dictionary()

