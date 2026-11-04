# Automotive Supply Chain Network Analysis

This project aims to build a multi-tier automotive supply-chain network using Refinitiv Value Chain datasets. The pipeline automatically ingests raw Excel exports for focal Original Equipment Manufacturers (OEMs), cleans them, standardizes relationships, and outputs a format ready for import into Neo4j graph databases.

## Understanding the Raw Data
The raw data comes from Refinitiv Workspace's Value Chain exports for individual automotive focal companies.
- **Supplier**: In the raw data, this indicates that the counterparty supplies parts, services, or materials to the focal OEM. (i.e. Counterparty `->` Focal OEM)
- **Customer**: In the raw data, this indicates that the focal OEM sells products or services to the counterparty. (i.e. Focal OEM `->` Counterparty)

## Graph Data Model

The Neo4j database uses a single label `(:Company)` to represent all entities in the network (both OEMs and counterparties), uniquely identified by `company_id`.

**Node Properties (`company_id` is the unique key):**
- `company_id`
- `company_name`
- `company_type`
- `country_region`
- `industry`

**Relationships:**
- **`(:Company)-[:SUPPLIES]->(:Company)`**: Represents a supplier relationship.
- **`(:Company)-[:SELLS_TO]->(:Company)`**: Represents a customer relationship.

Each relationship includes metadata to trace provenance: `confidence_pct`, `freshness`, `source_tier`, and `source_filename`.

## What is Tier 1?
In this iteration, all collected data represents **Tier 1 (Direct)** relationships relative to the focal company from which the data was exported. We do not infer multi-tier relationships (e.g. Tier 2, Tier 3) purely from company names. 

**Future Expansion (Multi-Tier):**
To build Tier 2 and Tier 3 networks, you will collect Refinitiv exports for the Tier 1 companies discovered here. When new data is dropped into the input folder, the `source_tier` variable in the script can be updated, linking the graph recursively based on authoritative company IDs.

## How the Cleaning Script Works
1. **Dynamic File Processing**: Iterates through all Excel files in the `input/` or `datasets btp1/` directory. It dynamically locates the actual header row (ignoring Refinitiv's metadata headers) and extracts the authoritative `Company Id` for the focal company.
2. **Duplicate Detection**: Safely identifies if multiple files exist for the same focal OEM, selects the most complete/recent export as canonical, and isolates duplicates to prevent redundant graph edges.
3. **Standardization**:
    - Converts company IDs strictly to string format (preventing scientific notation or float conversion).
    - Normalizes Confidence Scores to a clean 0-100 scale.
    - Standardizes date formats and column names to `snake_case`.
4. **Graph Preparation**: Generates nodes (`companies.csv`) and directional edges (`relationships.csv`, split into `SUPPLIES` and `SELLS_TO`).

## Directory Structure
- `datasets btp1/` or `input/`: Contains the raw Refinitiv Excel files.
- `cleaned/individual/`: Contains cleaned CSVs for each individual focal company.
- `cleaned/graph_ready/`: Contains `companies.csv` and relationship files ready for Neo4j Data Importer.
- `cleaned/reports/`: Contains data quality reports and an execution summary.
- `scripts/`: Contains the cleaning Python script `clean_refinitiv_value_chains.py`.

## Rerunning the Pipeline
To rerun the data extraction and cleaning pipeline, simply execute:
```bash
python scripts/clean_refinitiv_value_chains.py
```
Outputs will be automatically regenerated in the `cleaned/` directory.

## Importing to Neo4j
1. Open the Neo4j Data Importer (or Neo4j Workspace).
2. Upload the files in `cleaned/graph_ready/`.
3. Create a `Company` node and map properties from `companies.csv` (using `company_id` as the ID).
4. Create `SUPPLIES` relationships mapping from `start_id` to `end_id` using `relationships_supplies.csv`.
5. Create `SELLS_TO` relationships mapping from `start_id` to `end_id` using `relationships_sells_to.csv`.
6. Run the import.
