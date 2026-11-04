# Deterministic Graph-Analysis Contract

The analytical layer provides deterministic querying and traversal capabilities over the SCDM Neo4j graph. It operates strictly on validated topology and requires no external models or agents.

## 1. Entity Resolution (`ResolutionResult`)
The `EntityResolver` provides deterministic mapping of user inputs to canonical `company_id`s.

- **Focal-Company Semantics:** Resolves a query using a strict hierarchy: Exact ID > Exact Normalized Name > Normalized Contains Search.
- **Resolution States:**
  - `RESOLVED`: A single exact or unambiguous match was found.
  - `AMBIGUOUS`: Multiple graph nodes matched the query (e.g., searching for "Volkswagen" yields both "Volkswagen AG" and "Volkswagen Group of America Inc"). Requires user or agent clarification.
  - `UNRESOLVED`: No matching nodes exist in the graph.

## 2. Supplier Traversal (`ExposureResult`)
The `GraphTraversal` service extracts upstream supply chains rooted at a specific focal company.

- **Graph Direction:** Upstream traversal always follows the source semantics: `(Supplier)-[SUPPLIES|SELLS_TO]->(Customer)`. When querying from a focal company, the query traverses backwards (incoming edges).
- **Tier Semantics:** Tiers are entirely **dynamic** and **relative** to the focal company being queried.
  - Distance 1 = Tier 1 (Immediate Supplier)
  - Distance 2 = Tier 2 (Supplier to Tier 1)
  - Distance N = Tier N
- There are no permanent global `Tier` labels on nodes. A company can simultaneously be Tier 1 for OEM A and Tier 3 for OEM B.
- **Max-Depth Behavior:** Traversals are strictly bounded by `max_depth` (default 3, configured via centralized `config`). The query utilizes shortest-depth guarantees provided by Cypher variable-length paths (`*1..N`).
- **Path Representation:** Paths are deduplicated topologically (node sequence). If multiple identical topological paths exist due to relationship metadata multiplicity (different observations of the same edge), they are collapsed into a single `SupplierPath`.
- **Exposure States:**
  - `RESOLVED`: Paths were successfully found.
  - `NO_GRAPH_EXPOSURE`: The focal company exists, but has no upstream suppliers in the graph up to the specified depth.
  - `UNRESOLVED`: The focal company does not exist.

## 3. Non-Goals / Exclusions
This layer intentionally **does not**:
- Infer or predict undocumented supply chain links.
- Infer whether a supplier is actively "disrupted".
- Perform automated external web searches.
- Execute fuzzy spelling correction using LLMs.
- Compute global supplier risk scores (reserved for Phase 5/6).
