import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent
GRAPH_DIR = PROJECT_ROOT / 'cleaned' / 'graph_ready'
ANALYSIS_DIR = PROJECT_ROOT / 'analysis'
CHARTS_DIR = ANALYSIS_DIR / 'charts'

ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Load data
companies = pd.read_csv(GRAPH_DIR / 'companies.csv', dtype={'company_id': str})
rels_supplies = pd.read_csv(GRAPH_DIR / 'relationships_supplies.csv', dtype={'start_id': str, 'end_id': str})
rels_all = pd.read_csv(GRAPH_DIR / 'relationships.csv', dtype={'start_id': str, 'end_id': str})

# Step 1: Supplier Universe (start_id in SUPPLIES are suppliers, end_id are OEMs)
supplies_df = rels_supplies.copy()
supplies_df['confidence_pct'] = pd.to_numeric(supplies_df['confidence_pct'], errors='coerce')
supplies_df['freshness'] = pd.to_numeric(supplies_df['freshness'], errors='coerce')
supplies_df['snippet_count'] = pd.to_numeric(supplies_df['snippet_count'], errors='coerce')

# Aggregating per supplier
supplier_gb = supplies_df.groupby('start_id')

supplier_universe = []

# Merge companies metadata to easily get names
comp_dict = companies.set_index('company_id').to_dict('index')

for supplier_id, group in supplier_gb:
    meta = comp_dict.get(supplier_id, {})
    
    oems = group['end_id'].unique()
    oem_names = group['source_company_name'].unique()
    
    mean_conf = group['confidence_pct'].mean()
    min_conf = group['confidence_pct'].min()
    max_conf = group['confidence_pct'].max()
    high_conf = (group['confidence_pct'] >= 80).sum()
    vhigh_conf = (group['confidence_pct'] >= 90).sum()
    
    mean_fresh = group['freshness'].mean()
    min_fresh = group['freshness'].min()
    fresh_4_5 = (group['freshness'] >= 4).sum()
    fresh_4_5_pct = (fresh_4_5 / len(group)) * 100 if len(group) > 0 else 0
    
    tot_snippets = group['snippet_count'].sum()
    mean_snippets = group['snippet_count'].mean()
    
    # Degrees in current network
    out_supply = len(rels_all[(rels_all['start_id'] == supplier_id) & (rels_all['relationship'] == 'SUPPLIES')])
    in_supply = len(rels_all[(rels_all['end_id'] == supplier_id) & (rels_all['relationship'] == 'SUPPLIES')])
    tot_supply_degree = out_supply + in_supply
    
    supplier_universe.append({
        'company_id': supplier_id,
        'company_name': meta.get('company_name', 'UNKNOWN'),
        'country_region': meta.get('country_region', 'UNKNOWN'),
        'industry': meta.get('industry', 'UNKNOWN'),
        'company_type': meta.get('company_type', 'UNKNOWN'),
        'number_of_oems_supplied': len(oems),
        'number_of_direct_oem_relationships': len(group),
        'oem_list': ", ".join(sorted([str(x) for x in oem_names if pd.notna(x)])),
        'average_confidence': mean_conf,
        'minimum_confidence': min_conf,
        'maximum_confidence': max_conf,
        'high_confidence_relationship_count': high_conf,
        'very_high_confidence_relationship_count': vhigh_conf,
        'average_freshness': mean_fresh,
        'minimum_freshness': min_fresh,
        'freshness_4_or_5_count': fresh_4_5,
        'freshness_4_or_5_pct': fresh_4_5_pct,
        'total_snippet_count': tot_snippets,
        'average_snippet_count': mean_snippets,
        'observed_out_degree_supply': out_supply,
        'observed_in_degree_supply': in_supply,
        'observed_supplier_total_degree': tot_supply_degree,
        'unique_focal_oems_connected': len(oems)
    })

df_suppliers = pd.DataFrame(supplier_universe)

# Step 7: Automotive Relevance
auto_high_keywords = ['auto', 'vehicle', 'transportation', 'battery', 'semiconductor', 'electronic', 'machinery', 'steel', 'aluminum', 'chemical', 'rubber']
auto_medium_keywords = ['software', 'it services', 'hardware', 'equipment', 'manufacturing', 'logistics', 'materials']

def categorize_industry(ind):
    if pd.isna(ind) or ind == 'UNKNOWN':
        return 'UNKNOWN'
    ind_lower = str(ind).lower()
    for kw in auto_high_keywords:
        if kw in ind_lower:
            return 'HIGH'
    for kw in auto_medium_keywords:
        if kw in ind_lower:
            return 'MEDIUM'
    return 'LOW'

df_suppliers['industry_relevance'] = df_suppliers['industry'].apply(categorize_industry)

# Step 9: Shared Supplier Score
# Based primarily on number of distinct focal OEMs supplied
df_suppliers['shared_oem_score'] = df_suppliers['number_of_oems_supplied']

# Step 10: Create Tier-1 Expansion Score
# Weights: Coverage 30%, Degree 20%, Relevance 15%, Confidence 15%, Freshness 10%, Evidence 5%, Geography 5%

# Normalize functions
def norm(series):
    s_min = series.min()
    s_max = series.max()
    if s_max == s_min:
        return np.zeros(len(series))
    return (series - s_min) / (s_max - s_min) * 100

score_coverage = norm(df_suppliers['number_of_oems_supplied'])
score_degree = norm(df_suppliers['observed_supplier_total_degree'])

rel_map = {'HIGH': 100, 'MEDIUM': 50, 'LOW': 0, 'UNKNOWN': 0}
score_relevance = df_suppliers['industry_relevance'].map(rel_map)

score_conf = norm(df_suppliers['average_confidence'].fillna(0))
score_fresh = norm(df_suppliers['average_freshness'].fillna(0))
score_evid = norm(df_suppliers['total_snippet_count'].fillna(0))

# Geography score: If supplies OEMs in different countries, higher score.
# We need OEMs countries. For simplicity, just use number of OEMs as a proxy for geo reach, or simply use 50 if they have 2+ OEMs
score_geo = (df_suppliers['number_of_oems_supplied'] > 1).astype(int) * 100

df_suppliers['network_score'] = score_degree

df_suppliers['expansion_score'] = (
    score_coverage * 0.30 +
    score_degree * 0.20 +
    score_relevance * 0.15 +
    score_conf * 0.15 +
    score_fresh * 0.10 +
    score_evid * 0.05 +
    score_geo * 0.05
)

# Ranking
df_suppliers = df_suppliers.sort_values(by='expansion_score', ascending=False).reset_index(drop=True)
df_suppliers['rank'] = df_suppliers.index + 1

# Step 13: Greedy Coverage Algorithm
greedy_selected = []
covered_oems = set()
remaining_suppliers = df_suppliers.copy()

while len(greedy_selected) < 100 and not remaining_suppliers.empty:
    best_idx = None
    best_new_oems = -1
    best_score = -1
    
    for idx, row in remaining_suppliers.iterrows():
        oem_list = set(row['oem_list'].split(', '))
        new_oems = len(oem_list - covered_oems)
        
        if new_oems > best_new_oems:
            best_new_oems = new_oems
            best_score = row['expansion_score']
            best_idx = idx
        elif new_oems == best_new_oems and row['expansion_score'] > best_score:
            best_score = row['expansion_score']
            best_idx = idx
            
    if best_idx is not None:
        selected_row = remaining_suppliers.loc[best_idx]
        greedy_selected.append(selected_row)
        covered_oems.update(set(selected_row['oem_list'].split(', ')))
        remaining_suppliers = remaining_suppliers.drop(best_idx)
    else:
        break
        
# If greedy doesn't reach 100 (e.g. no more new OEMs to add), backfill with top score
if len(greedy_selected) < 100:
    for idx, row in remaining_suppliers.iterrows():
        greedy_selected.append(row)
        if len(greedy_selected) >= 100:
            break

greedy_df = pd.DataFrame(greedy_selected).reset_index(drop=True)
greedy_df['greedy_rank'] = greedy_df.index + 1

# Priority Classification (Top 20% = A, Next 30% = B, Remaining = C)
def classify_priority(rank, total):
    if rank <= total * 0.2:
        return 'A'
    elif rank <= total * 0.5:
        return 'B'
    return 'C'

greedy_df['priority'] = [classify_priority(r, len(greedy_df)) for r in greedy_df['greedy_rank']]

# Step 14: Save Top 50, 75, 100
keep_cols = [
    'greedy_rank', 'company_id', 'company_name', 'country_region', 'industry', 'industry_relevance',
    'number_of_oems_supplied', 'oem_list', 'average_confidence', 'minimum_confidence',
    'average_freshness', 'freshness_4_or_5_pct', 'total_snippet_count', 'observed_supplier_total_degree',
    'shared_oem_score', 'network_score', 'expansion_score', 'priority'
]

# Write CSVs safely
for k in [50, 75, 100]:
    if k <= len(greedy_df):
        greedy_df.head(k)[keep_cols].rename(columns={'greedy_rank': 'rank', 'number_of_oems_supplied': 'oem_count', 'observed_supplier_total_degree': 'observed_supply_degree'}).to_csv(ANALYSIS_DIR / f'TOP_{k}_TIER1_EXPANSION_TARGETS.csv', index=False)

# EDA Reports
df_suppliers.to_csv(ANALYSIS_DIR / 'tier1_supplier_eda.csv', index=False)
greedy_df.to_csv(ANALYSIS_DIR / 'tier1_supplier_rankings.csv', index=False)

country_summary = df_suppliers['country_region'].value_counts().reset_index()
country_summary.columns = ['Country', 'Count']
country_summary.to_csv(ANALYSIS_DIR / 'tier1_supplier_country_summary.csv', index=False)

ind_summary = df_suppliers['industry'].value_counts().reset_index()
ind_summary.columns = ['Industry', 'Count']
ind_summary.to_csv(ANALYSIS_DIR / 'tier1_supplier_industry_summary.csv', index=False)

oem_cov = df_suppliers['number_of_oems_supplied'].value_counts().sort_index().reset_index()
oem_cov.columns = ['OEMs_Supplied', 'Supplier_Count']
oem_cov.to_csv(ANALYSIS_DIR / 'tier1_oem_coverage_summary.csv', index=False)

df_suppliers['average_confidence'].dropna().to_csv(ANALYSIS_DIR / 'tier1_confidence_distribution.csv', index=False)
df_suppliers['average_freshness'].dropna().to_csv(ANALYSIS_DIR / 'tier1_freshness_distribution.csv', index=False)

# Step 16: Visualizations

# 1. Number of Tier-1 suppliers by OEM
plt.figure(figsize=(10,6))
oem_counts = rels_supplies['source_company_name'].value_counts()
sns.barplot(y=oem_counts.index, x=oem_counts.values, palette='viridis')
plt.title('Number of Tier-1 Suppliers by OEM')
plt.xlabel('Count')
plt.ylabel('OEM')
plt.tight_layout()
plt.savefig(CHARTS_DIR / 'suppliers_by_oem.png')
plt.close()

# 2. Distribution of OEM coverage per supplier
plt.figure(figsize=(8,5))
sns.countplot(data=df_suppliers, x='number_of_oems_supplied', palette='Set2')
plt.title('Distribution of OEM Coverage per Supplier')
plt.xlabel('Number of Focal OEMs Supplied')
plt.ylabel('Number of Suppliers')
plt.tight_layout()
plt.savefig(CHARTS_DIR / 'oem_coverage_distribution.png')
plt.close()

# 3. Top shared suppliers
plt.figure(figsize=(10,6))
top_shared = df_suppliers.sort_values(by='number_of_oems_supplied', ascending=False).head(15)
sns.barplot(y=top_shared['company_name'], x=top_shared['number_of_oems_supplied'], palette='magma')
plt.title('Top 15 Shared Suppliers by OEM Coverage')
plt.xlabel('Number of OEMs Supplied')
plt.tight_layout()
plt.savefig(CHARTS_DIR / 'top_shared_suppliers.png')
plt.close()

# 4. Top suppliers by expansion score
plt.figure(figsize=(10,6))
top_exp = df_suppliers.head(15)
sns.barplot(y=top_exp['company_name'], x=top_exp['expansion_score'], palette='rocket')
plt.title('Top 15 Suppliers by Expansion Score')
plt.xlabel('Expansion Score (0-100)')
plt.tight_layout()
plt.savefig(CHARTS_DIR / 'top_expansion_targets.png')
plt.close()

# 5. Supplier country distribution
plt.figure(figsize=(10,6))
sns.barplot(y='Country', x='Count', data=country_summary.head(15), palette='mako')
plt.title('Top 15 Supplier Countries')
plt.tight_layout()
plt.savefig(CHARTS_DIR / 'supplier_country_distribution.png')
plt.close()

# 6. Supplier industry distribution
plt.figure(figsize=(10,6))
sns.barplot(y='Industry', x='Count', data=ind_summary.head(15), palette='cubehelix')
plt.title('Top 15 Supplier Industries')
plt.tight_layout()
plt.savefig(CHARTS_DIR / 'supplier_industry_distribution.png')
plt.close()

# 7. Confidence distribution
plt.figure(figsize=(8,5))
sns.histplot(df_suppliers['average_confidence'].dropna(), bins=20, kde=True, color='blue')
plt.title('Distribution of Average Confidence Score')
plt.xlabel('Confidence (%)')
plt.tight_layout()
plt.savefig(CHARTS_DIR / 'confidence_distribution.png')
plt.close()

# 8. Freshness distribution
plt.figure(figsize=(8,5))
sns.histplot(df_suppliers['average_freshness'].dropna(), bins=5, kde=False, color='green')
plt.title('Distribution of Average Freshness Score')
plt.xlabel('Freshness Score (1-5)')
plt.tight_layout()
plt.savefig(CHARTS_DIR / 'freshness_distribution.png')
plt.close()

# Step 17 & 18: Markdown Report
report_md = f"""# Tier-1 Expansion EDA & Prioritization Report

## 1. Dataset Overview
This analysis investigates the Tier-1 automotive supply-chain dataset to identify the optimal targets for Tier-2 expansion.
- **Number of Focal OEMs**: {len(rels_supplies['source_company_name'].unique())}
- **Number of Unique Tier-1 Suppliers**: {len(df_suppliers)}
- **Number of Supplier Relationships (SUPPLIES)**: {len(rels_supplies)}
- **Number of Suppliers Shared Across Multiple OEMs**: {len(df_suppliers[df_suppliers['number_of_oems_supplied'] > 1])}

## 2. Geography & Industry
- **Top Countries**: {', '.join(country_summary['Country'].head(5).tolist())}
- **Top Industries**: {', '.join(ind_summary['Industry'].head(5).astype(str).tolist())}

## 3. Data Quality (Confidence & Freshness)
- Average Confidence: {df_suppliers['average_confidence'].mean():.2f}%
- Average Freshness Score: {df_suppliers['average_freshness'].mean():.2f} / 5

## 4. Ranking Methodology
Suppliers were ranked using a weighted 0-100 expansion score incorporating:
- OEM Coverage (30%)
- Observed Network Degree (20%)
- Automotive Industry Relevance (15%)
- Relationship Confidence (15%)
- Freshness (10%)
- Evidence / Snippet Count (5%)
- Geographic / Cross-border proxy (5%)

A **greedy coverage algorithm** was then applied to select the TOP 50, 75, and 100 targets. Instead of just picking the highest scores (which might all supply the same OEM), the greedy approach selects the next best supplier that adds connections to focal OEMs not yet covered by the target list.

## 5. Priority Classification
- **Priority A (Top 20%)**: Crucial cross-network bottlenecks and high-relevance nodes.
- **Priority B (Next 30%)**: Strong tier-1 suppliers with good confidence and connectivity.
- **Priority C**: High-quality suppliers providing niche or specific OEM coverage.

## 6. Recommendations for Tier-2 Collection

### Primary Recommendation: TOP 50 List
Collecting the Value Chain data for these 50 suppliers will provide a highly diversified Tier-2 foundation.
- OEMs connected via these targets: {len(set(', '.join(greedy_df.head(50)['oem_list']).split(', ')))}
- Total direct relationships represented: {greedy_df.head(50)['number_of_direct_oem_relationships'].sum()}
- Unique Countries: {greedy_df.head(50)['country_region'].nunique()}

### Alternative Recommendation: TOP 100 List
For a broader expansion covering a long tail of regional or specialized suppliers.
- OEMs connected via these targets: {len(set(', '.join(greedy_df.head(100)['oem_list']).split(', ')))}
- Total direct relationships represented: {greedy_df.head(100)['number_of_direct_oem_relationships'].sum()}
- Unique Countries: {greedy_df.head(100)['country_region'].nunique()}

*Note: All output CSV files and visual charts are available in the `analysis/` directory.*
"""

with open(ANALYSIS_DIR / 'TIER1_EXPANSION_EDA_REPORT.md', 'w') as f:
    f.write(report_md)

# Terminal logs
print("==================================================")
print("TIER-1 SUPPLIER EDA & PRIORITIZATION COMPLETE")
print("==================================================")
print(f"Total Tier-1 Suppliers Evaluated: {len(df_suppliers)}")
print(f"Total Shared Suppliers (>1 OEM): {len(df_suppliers[df_suppliers['number_of_oems_supplied'] > 1])}")
print("\nValidation Checks:")
print(f"- No missing IDs in Top 100: {not greedy_df.head(100)['company_id'].isna().any()}")
print(f"- No duplicates in Top 100: {greedy_df.head(100)['company_id'].is_unique}")
print(f"- Min Expansion Score in Top 100: {greedy_df.head(100)['expansion_score'].min():.2f}")

print("\n--------------------------------------------------")
print("RECOMMENDED TOP 50 EXPANSION TARGETS")
print("--------------------------------------------------")
print(greedy_df.head(50)[['greedy_rank', 'company_name', 'number_of_oems_supplied', 'expansion_score', 'priority']].to_string(index=False))

print("\nOutputs saved to:")
print(str(ANALYSIS_DIR))

