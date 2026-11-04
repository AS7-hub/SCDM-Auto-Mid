# Project Audit Report

## 1. Verified Facts

### Filesystem & Data
- **Project Directory**: `C:\Users\arkap\OneDrive\Documents\SCDM Auto Mid` is empty. We are starting entirely from scratch here.
- **Dataset Directory**: `C:\Users\arkap\OneDrive\Documents\SCDM AUTO data` contains raw `.xlsx` files and a cleaned dataset output under `LSEG_CLEANED_OUTPUT\03_GRAPH_READY`.
- **Raw Data Format**: Excel files with Refinitiv Value Chains data. The first 4 rows contain metadata. Actual headers start on row 4.
- **Cleaned Data Quality**:
  - `companies_latest.csv`: 1,933 rows. 0 duplicate IDs. 17 duplicate names. Missing `company_name` (6) and `country_region` (21).
  - `relationships_sells_to_latest.csv`: 1,655 rows. 29 duplicate edges. No orphan endpoints.
  - `relationships_supplies_latest.csv`: 1,881 rows. 25 duplicate edges. No orphan endpoints.

### Neo4j Graph Database
- **Status**: Running locally on `bolt://127.0.0.1:7687` (Note: old `.env` incorrectly listed `7689`).
- **Graph State**:
  - **Nodes**: 2,909 `Company` nodes.
  - **Relationships**: 3,283 `SUPPLIES` and 1,971 `SELLS_TO`.
  - **Constraints/Indexes**: Uniqueness constraint and index exist on `Company.company_id`.
  - **Contamination**: No `PackageRust` nodes were found.

### Environment & Tooling
- **Python**: 3.11.9
- **Dependencies**: `pandas`, `networkx`, `openpyxl` are available. **Missing**: `neo4j`, `langgraph`, `pydantic`, `pytest`.
- **APIs**: Gemini API is accessible and authenticated successfully with the existing key from the old `.env`.

## 2. Unresolved Questions
- **Database Mismatch**: The live Neo4j database has 2,909 nodes, but the latest cleaned CSVs only have 1,933 nodes. It is unclear if the current Neo4j database contains legacy data or if the CSVs are a subset of a broader ingestion.
- **Duplicate Edges**: There are duplicate edges in the cleaned CSVs for both `SELLS_TO` and `SUPPLIES`. Should the new pipeline merge these or keep them separate?

## 3. Blockers
- None currently. The ground truth has been established.

## 4. Recommendations for Next Implementation Step
1. **Initialize Project & Env**: Create a fresh `pyproject.toml` or `requirements.txt` in the new project directory, specifically installing `neo4j`, `langgraph`, `pydantic`, etc.
2. **Setup Config**: Create a new `.env` file pointing to `bolt://127.0.0.1:7687` instead of `7689`.
3. **Database Decision**: Decide whether to wipe the existing Neo4j database to match the current CSV exports, or keep it as is.
4. **Data Ingestion Script**: Design the new ingestion logic to handle the 4-row metadata offset in the raw Excel files and gracefully handle the missing names/regions.
