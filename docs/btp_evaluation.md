# SCDM BTP Evaluation Report

## 1. Objective
This document provides empirical evaluation evidence for the Supply Chain Disruption Monitor (SCDM) to the Business Technology Platform (BTP) stakeholders. It details the actual performance, data integrity, and deterministic guarantees of the implemented architecture.

## 2. Dataset & Ground Truth Statistics
The evaluation uses the canonical LSEG-derived automotive supply chain graph.

### Final Graph Snapshot (Valid as of Phase 11)
- **Total Company Nodes**: 1933
- **Total Relationships**: 3482
- **SUPPLIES Relationships**: 1856
- **SELLS_TO Relationships**: 1626
- **Unique Company IDs**: 1933
- **Duplicate Company IDs**: 0 (Graph integrity is 100%)

## 3. Experimental Setup & Resolution
The entity resolution uses exact fuzzy matching backed by direct Neo4j index queries.
*   **Resolved Rate**: High accuracy for known aliases (e.g., "Microsoft Corporation" and "Microsoft" successfully resolve to ID `4295907168`).
*   **Unresolved Handing**: Unknown queries (e.g., "NonExistentCorp123") correctly fall into `UNRESOLVED` status.
*   **Average Resolution Latency**: ~0.013s per query.

## 4. Multi-tier Traversal Evaluation
For a tested focal company ("Microsoft", ID `4295907168`) exposed to depth 3:
- **Paths Discovered**: 1103 paths
- **Tier 1 Suppliers**: 5
- **Tier 2 Suppliers**: 360
- **Tier 3 Suppliers**: 328
- **Traversal Runtime**: ~0.134s (Extremely performant due to Neo4j graph locality)

## 5. Workflow & Approval Evaluation
- **MOCK Mode**: Successfully runs end-to-end bypassing live LLM dependencies, producing reproducible, synthetically constrained reports.
- **Approval Gating**: Gating is perfectly enforced. The LangGraph workflow (`should_continue_sourcing`) structurally blocks Agent 7 (Alternative Sourcing) execution unless the human input is explicitly `y` (`APPROVED`).
- **DEMO Error Handling**: If required API credentials are missing, the system hard-fails deterministically rather than substituting mock logic, ensuring live environments do not produce hallucinated outputs.

## 6. LLM Budget Observations
LLM calls are strongly bounded to prevent runaway cloud costs. 
- A standard workflow consumes 3 explicit `gemini` structured generation calls.
- Exceeding the configurable budget triggers a `LLMBudgetExceededError` cleanly handling failure states.

## 7. Limitations & Missing Capabilities (Not Scientifically Validated)
The system is implemented as designed, but stakeholders must be aware of the following data-limited boundaries:
1.  **Prediction vs Proxies**: The Early Warning model is a *current-state topological proxy* (Scarcity & Opacity). It does **not** predict disruptions probabilistically because true historical supplier outcomes do not exist in the source data.
2.  **Product Associations**: Agent 3 connects companies to materials using external retrieval. It does **not** validate true manufacturing capabilities or complete BOM hierarchies.
3.  **Alternative Sourcing Validation**: Discovered candidates are checked for graph connectivity, but their commercial feasibility (e.g., capacity, geography, contracts) is strictly beyond the scope of this model.
