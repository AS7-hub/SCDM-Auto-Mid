# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Phase 11: Evaluation, Reproducibility, Security Hygiene & BTP Readiness**
- `scripts/evaluate.py`: Deterministic evaluation harness for graph integrity and resolution speed.
- `scripts/run_btp_demo.py`: Automated, repeatable BTP presentation runner for MOCK/DEMO modes.
- `docs/reproducibility.md`: Clear reproduction steps free of API secrets.
- `docs/btp_evaluation.md`: Formal business technology platform evaluation report.
- `LLMClient.get_telemetry()`: Added telemetry exposing attempted, successful, and remaining budget metrics.

### Added (Agent 3 - Product Search)
- Implemented ProductSearchAgent and integrated into LangGraph.
- Verified Agent 3 with MOCK reporting.

### Added
- **Phase 9: Final Hardening & Extensibility**
- Agent 4: Network Visualizer payload generation based on deterministic graph paths and risk scores.
- Executive Reporting layer (`executive_report.py`) for clean, factual CLI outputs distinguishing LLM interpretation from graph facts.
- Early Warning / Temporal Vulnerability indicators (topological proxies: depth opacity, topological scarcity).
- Explicit `DEMO` mode failure harness (hard failure if API key is missing).
- Graph workflow conditional edge hardening and explicit error paths for unresolvable entities.

### Changed
- `__main__.py` to use `executive_report` instead of inline printing.
- `client.py` strictly adheres to `config.gemini_model`.
- `graph.py` resolves focal company dynamically or fails fast. DuckDuckGo retrieval and Gemini extraction to ground product/material claims in explicit external evidence.
- Expanded `EvidenceClaim` schema to store subject, predicate, object, claim text, sources, and uncertainty logic.
- Integrated product search into the LangGraph workflow (`node_product_search`) between Disruption Understanding and Entity Resolution.
- Successfully verified Mock mode execution end-to-end and added Agent 3 unit tests (`tests/test_product_search.py`).

### Added (Agent 7 - Alternative Sourcing)
- Completed `AlternativeSourcingAgent` by integrating `EntityResolver` and a new `check_supplier_connectivity` deterministic graph query from `GraphTraversal`.
- Implemented a deterministic sourcing qualification formula based purely on topological features (graph presence, shortest distance to focal company, global downstream out-degree).
- Candidates are strictly evaluated and assigned appropriate status boundaries (`VALIDATED_CLAIM`, `REVIEW_NEEDED`) preventing LLMs from fabricating supply chain facts.
- Integrated safety tests asserting Alternative Sourcing respects upstream graph failures, ambiguous identity resolution, and strictly adheres to LangGraph approval boundaries.

### Fixed & Stabilized (Phase 7-8 Stabilization)
- Fixed MOCK CLI defect: updated `MockTraversal.get_upstream_exposure` and `MockRiskEngine.calculate_risk` in `src/scdm/__main__.py` to match exact production interfaces. MOCK mode now successfully streams to terminal state.
- Added comprehensive unit tests for `src/scdm/workflow/graph.py` to test LangGraph routing, deterministic risk persistence, LLM budget enforcement, LLM fallbacks, and conditional boundaries (in `tests/test_workflow.py`).
- Added robust error handling in `node_graph_traversal` to catch missing `focal_company_id` without silent crashing.
- Added CLI interface tests for MOCK mode, human approval callbacks, and argument validation (in `tests/test_cli.py`).
- Kept human approval as a synchronous `cli_approval_callback` boundary to prioritize stability over a complex persistent LangGraph checkpointer for now.
- Ensured Agent 7 stub variables `graph_presence=False` and `ranking_score=0.0` remain isolated to prevent misinterpretation of alternative supplier qualification.

### Verified & Audited
- Conducted architectural ground-truth audit of implemented components against the 7-agent target architecture.
- Verified Agent 1 (`DisruptionMonitorAgent` in `src/scdm/agents/disruption_monitor.py`), Agent 6 (`CSCOAgent` in `src/scdm/agents/csco.py`), and deterministic risk/graph engines.
- Verified that Agent 3 (Product Search) and Agent 4 (Network Visualizer) are completely NOT IMPLEMENTED.
- Identified that Agent 7 (Alternative Sourcing) is only partially implemented (graph presence checking and candidate ranking are stubbed with defaults).
- Identified that LangGraph orchestration (`src/scdm/workflow/graph.py`) has 0% automated test coverage, uses synchronous callbacks rather than persistent checkpoint-based interrupts, and lacks error-recovery routing.
- Identified defect in `src/scdm/__main__.py`: `MockTraversal` and `MockRiskEngine` implement mismatched method signatures (`find_upstream_suppliers` vs `get_upstream_exposure`, `calculate_supplier_risk` vs `calculate_risk`), causing CLI MOCK mode execution to crash.

### Added
- Created `scdm.retrieval.search.DuckDuckGoSearchProvider` utilizing the `ddgs` package to provide bounded, safely-cached external search functionality.
- Implemented `EvidenceSource` and `EvidenceClaim` in `schemas.py` to deterministically track search states (`NO_SEARCH_RESULTS`, `TIMEOUT`, etc.) independently from LLM processing.
- Created `tests/test_retrieval.py` to enforce URL canonicalization, rate-limit fallback, and cache exhaustion testing without relying on live web calls during CI.
- Created `scdm.analysis.risk_engine.RiskEngine` implementing a purely deterministic topological risk score for Tier-1 suppliers using 5 weighted topological dimensions.
- Expanded `RiskResult` schema with detailed numeric features, normalization structures, and explicit reasons for complete score transparency.
- Added synthetic unit tests validating min-max scaling and zero-division bounds in `tests/test_risk_engine.py`.
- Developed explicit Risk Engine documentation outlining feature proxies (Path Concentration instead of Dependency Ratio) given the dataset constraints.
- Created `scdm.analysis.resolution.EntityResolver` implementing strict exact-match and normalized contains-match focal company mapping with defined deterministic resolution states.
- Created `scdm.analysis.traversal.GraphTraversal` implementing bounded depth Cypher path searches, converting graph structure dynamically into relative Tier groups while natively deduplicating equivalent topologies.
- Added structured models `ExposureResult`, `SupplierPath`, and `ResolutionResult` in `schemas.py` to strictly separate the deterministic Neo4j graph response from the upcoming LLM processing layers.
- Published `docs/analytical_contract.md` defining strict traversal rules, dynamic tier rules, and explicit non-goals for this layer.
- Created `scripts/backup_neo4j.py` to deterministically snapshot nodes and relationships to local JSON files.
- Created `scripts/reset_neo4j.py` to perform a controlled `DETACH DELETE` of the legacy default Neo4j database.
- Created `scripts/execute_load.py` which orchestrates graph loading and enforces an idempotency test.
- Created `tests/test_graph_integrity.py` to actively query Neo4j and rigorously validate graph topology.
- Created `scdm.data.graph_loader.py` with idempotent `MERGE`-based node and relationship loading logic to safely load the graph.
- Designed `run_pre_flight_checks()` to validate graph integrity (duplicate detection, endpoint existence).

### Changed
- **Phase 4 Execution**: Fully wiped the compromised Neo4j graph and successfully rebuilt it as the authoritative SCDM graph using strictly the canonical dataset output from Step 3. The new graph perfectly mirrors the canonical layer (`1,933` unique company nodes and `3,482` total edges) with zero duplicates. Idempotency test proves that repeated loading runs safely update properties without modifying topology.

### Changed
- **Strategy Update**: Verified that the existing Neo4j graph (~2,909 nodes) contains severe duplication (only 2,053 unique `company_id`s) and is an indiscriminate blend of legacy `datasets btp1` and current `tier 1 top 50`. We established **Strategy C**: A clean reload of only the canonical data into Neo4j in the subsequent execution phase, maintaining data authority.
- Created data ingestion pipeline (`scdm.data.ingestion`, `scdm.data.normalization`, `scdm.data.validation`)
- Added header detection logic for raw LSEG/Refinitiv `.xlsx` files
- Added explicit deduplication rules for identical names with distinct IDs and equivalent relationship endpoints
- Automated generation of canonical and focal company CSVs
- Implemented robust `validation_report.json` logging 1933 nodes and 3482 relationships without data loss
- Added unit tests for normalization business logic (`tests/test_normalization.py`)

### Fixed
- Fixed raw file parsing that incorrectly merged metadata rows with actual headers (Step 2: Foundation)
- **Centralized Configuration**: Added `pydantic-settings` based config in `scdm.core.config.py` supporting `APP_MODE` (MOCK/DEMO/LIVE).
- **Environment**: Created `.env.example` defining necessary secrets without exposing them.
- **Dependencies**: Added `requirements.txt` with exact libraries (`pydantic`, `neo4j`, `langgraph`, `google-genai`, etc.).
- **Domain Schemas**: Created comprehensive Pydantic models for `Company`, `SupplyChainRelationship`, `DisruptionEvent`, `Evidence`, `GraphPath`, `RiskResult`, `Recommendation`, `AlternativeSupplier`, and `WorkflowState`.
- **Contracts**: Defined Enums for `DataLayer`, `RelationshipType`, `ApprovalState`, and `EvidenceStatus` to prevent LLM hallucinations from overriding deterministic state.
- **Tests**: Added focused unit tests for configuration loading, missing keys, and schema validation.

### Discovered (Ground-Truth Audit)
- **Project Directory**: Verified `C:\Users\arkap\OneDrive\Documents\SCDM Auto Mid` is completely blank.
- **Data Reality vs Graph Reality**: 
  - The cleaned CSVs in `LSEG_CLEANED_OUTPUT\03_GRAPH_READY` contain 1933 Company nodes and 3536 total relationships.
  - The live Neo4j database on `bolt://127.0.0.1:7687` contains 2909 Company nodes and 5254 total relationships. The database contains more data than the latest exports or is partially dirty from previous runs.
- **Neo4j Configuration**: The old project's `.env` incorrectly pointed to port `7689`. The actual running instance is on port `7687`. No `PackageRust` contamination was found.
- **Dataset Quirks**:
  - `company_name` has 6 missing values; `country_region` has 21 missing values.
  - There are 17 duplicate `company_name` entries but 0 duplicate `company_id`s.
  - Sells To has 29 duplicate relationships; Supplies has 25 duplicate relationships (by start/end IDs).
  - Raw Excel files have 4 rows of metadata before the actual headers begin.
- **Environment**: Python 3.11 is used. Required libraries like `pydantic`, `langgraph`, and `neo4j` are NOT installed in the base environment and must be added.
- **Gemini**: API is accessible and valid.
