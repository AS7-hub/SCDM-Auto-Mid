# Tier-2 LSEG Value Chain Cleaning Process

This directory contains the output of the automated cleaning pipeline for the Tier-2 Refinitiv/LSEG Value Chain files. The process programmatically parses raw Excel files, standardizes column formats, strictly maps supply-chain graph directionality, and generates Neo4j-ready output.

## Directory Structure
- **01_EDA/**: Contains the Pre-Cleaning Exploratory Data Analysis report (`01_EDA_REPORT.csv`) generated from dynamically scanning all 46 workbooks.
- **02_CLEANED_COMPANY_FILES/**: Contains 46 individual CSVs for each processed focal company, acting as a clean, granular audit trail of all extracted Refinitiv attributes.
- **03_GRAPH_READY/**: Contains the final merged dataset prepared for Neo4j import:
  - `companies.csv` (deduplicated Master Node table)
  - `focal_companies.csv` (list of OEM/Tier-1 focal node IDs)
  - `relationships.csv` (all edges combined)
  - `relationships_supplies.csv` (all `SUPPLIES` edges)
  - `relationships_sells_to.csv` (all `SELLS_TO` edges)
- **04_VALIDATION/**: Contains final validation logs and summaries.
  - `validation_summary.csv`: Core metrics of the processing pipeline.
  - `anomalies.csv`: Any invalid relationships, out-of-bounds metrics, or self-loops detected.
  - `company_identity_anomalies.csv`: Output tracking identity collisions if one Refinitiv ID maps to multiple different company names.
- **05_LOGS/**: Script execution logging.

## Methodology
1. **Dynamic Headers**: The script locates the actual tabular headers in each Excel sheet based on the `Identifier` and `Company Name` columns, ignoring extraneous leading Refinitiv metadata.
2. **Metadata Extraction**: Focal company ID and Name are extracted accurately from the workbook's internal preamble, preventing reliance on potentially inaccurate file names.
3. **Cleaning Operations**: Whitespace stripped, nulls normalized, dates converted to `YYYY-MM-DD`, and confidence scaled explicitly to 0-100 without dropping arbitrary records. IDs are aggressively type-cast as strings to prevent float degradation or scientific notation.
4. **Relationship Orientation Logic (Crucial)**: 
   - `Relationship == Supplier`: Translates to `counterpart` ──`SUPPLIES`──> `focal company`
   - `Relationship == Customer`: Translates to `focal company` ──`SELLS_TO`──> `counterpart`
5. **Deduplication**: Graph nodes (`companies.csv`) are strictly deduplicated by Refinitiv `company_id`. Relationships are preserved across workbooks to maintain edge provenance (`source_file` is attached to every relationship).

## Safety & Validation Rules
- **Fail Closed**: The script skips files safely with an error log if headers or critical identifiers cannot be found.
- **Read-Only**: The original directory (`tier 1 top 50`) is NEVER modified or written to.
- **Data Preservation**: Metrics like `confidence_pct`, `freshness`, and `snippet_count` are validated but NOT filtered, preserving all raw signals for downstream analytics.

## Execution Statistics
- 46 Input Files processed.
- 3536 Cleaned relationship rows generated.
- 1933 Unique Companies discovered.
- 0 Anomalous or structurally invalid records requiring quarantine.
