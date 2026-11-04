# SCDM: Final Architecture & Agentic Boundaries

## 1. System Objective
The Supply Chain Disruption Monitor (SCDM) framework is a multi-agent system designed to identify supply chain exposure to real-world disruptions, assess risks dynamically, and recommend alternative sourcing. The primary goal is to combine the reasoning capabilities of LLMs with the absolute factual reliability of a deterministic graph database.

## 2. Core Architecture Philosophy
The system enforces a strict boundary between **LLM Interpretation** (which reads unstructured data and extracts hypotheses) and **Deterministic Graph Facts** (which establish mathematical certainty regarding topology, relationship distance, and risk calculation).

## 3. Seven Conceptual Agents
1. **Agent 1 - Disruption Monitor**: Monitors unstructured text for disruption events (LLM).
2. **Agent 2 - Graph Traversal & Entity Resolution**: Exact-match or high-confidence string resolution, followed by strict deterministic graph traversal (Neo4j/Python).
3. **Agent 3 - Product Search**: *Evidence-Backed Product Association*. Retrieves external articles to link companies to specific materials. It does NOT hallucinate BOM catalogs.
4. **Agent 4 - Network Visualizer**: Deterministic generation of a serialized subgraph payload based on traversed exposure paths.
5. **Agent 5 - Risk Engine**: Deterministic calculation of exposure risk using topological features (Tier depth, degree centrality) and static confidence weights.
6. **Agent 6 - CSCO Decision Engine**: Summarizes risk context into structured recommendations (LLM).
7. **Agent 7 - Alternative Sourcing**: Discovers candidate alternative suppliers from external evidence and validates them strictly against the canonical graph for prior integration.

## 4. Deterministic vs LLM Responsibility Split
| Responsibility | Layer | Enforcer |
| :--- | :--- | :--- |
| **Extract Disruption** | LLM Interpretation | `disruption_monitor.py` |
| **Product Evidence** | LLM Interpretation | `product_search.py` |
| **Company Identity** | Deterministic Fact | `resolution.py` |
| **Supply Chain Topology** | Deterministic Fact | `traversal.py` (Neo4j) |
| **Risk Scoring** | Deterministic Calculation | `risk_engine.py` |
| **Alternative Recommendation** | LLM Extraction | `alternative_sourcing.py` |
| **Alternative Verification** | Deterministic Fact | `traversal.py` / Graph |

## 5. Known Limitations & Research Constraints
*   **Predictive ML**: The risk engine is a deterministic topological baseline. It does **NOT** represent probability of financial loss or statistically validated business risk.
*   **Alternative Sourcing Validation**: Graph-qualified alternative sourcing establishes topological connectivity and evidence-backed product claims. It does **NOT** constitute a procurement-ready substitute (capacity, geography, commercial terms are not assessed).
*   **Early Warning Framework**: True historical time-series data is largely unavailable in the static LSEG dataset. As such, the early warning system measures **Current-State Topological Proxies** (Depth Opacity, Scarcity) rather than conducting true longitudinal historical prediction.
*   **Human Approval**: The approval gate (`cli_approval_callback`) relies on a synchronous execution pause to enforce boundaries due to CLI constraints.

## 6. Execution Modes
*   `MOCK`: Fully deterministic. Bypasses live LLM and search calls, injecting fake external data to safely test workflow logic, formatting, and graph integrity.
*   `DEMO`: Live LLM / Live Graph. Will fail fast `ValueError` if API keys are missing. LLM calls are explicitly bounded by configurable budgets.
*   `LIVE`: Full-scale deployment (pending web-server persistence/checkpointers).
