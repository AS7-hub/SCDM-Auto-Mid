# SCDM: Reproducibility Guide

The Supply Chain Disruption Monitor (SCDM) framework is highly deterministic. Evaluators can reproduce the system's exact topological behavior without external API keys.

## 1. Prerequisites
- **Python**: `3.11+`
- **Neo4j**: `5.x+` (Running locally on `bolt://127.0.0.1:7687` by default)
- **Dataset**: The canonical automotive dataset must be loaded into Neo4j. (Use `python scripts/execute_load.py` if not loaded).

## 2. Dependencies
Install all required dependencies:
```bash
pip install -r requirements.txt
```

## 3. Environment & Secrets
No hard-coded secrets exist in the repository. Configuration is managed via Pydantic (`src/scdm/core/config.py`), reading from environment variables.
Copy `.env.example` to `.env` to configure your local credentials.

*   `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
*   `GEMINI_API_KEY` (Only required for DEMO/LIVE mode)

## 4. Execution Modes

### A. MOCK Mode (No API Keys Required)
MOCK mode runs the entire workflow offline, utilizing deterministic mock components that return fixed schema-compliant payloads. This allows you to verify graph traversals and workflow execution without spending API credits.
```bash
python -m scdm --focal-company "Ford Motor" --query "Shortage of Palladium" --mode MOCK
```

### B. DEMO Mode (API Keys Required)
DEMO mode initiates the actual LangGraph workflow, routing the query through Gemini and DuckDuckGo, before executing deterministically against the canonical Neo4j graph.
```bash
# Will safely raise a ValueError if GEMINI_API_KEY is not set.
python -m scdm --focal-company "Ford Motor" --query "Shortage of Palladium" --mode DEMO
```

### C. LIVE Mode
LIVE mode expands the API budgets and traversal depths, intended for production deployments with an asynchronous checkpointer for the human approval boundary.

## 5. Testing
The test suite spans all agents, deterministic rules, and workflow edge-cases. It does NOT require a live Neo4j database or API key to pass (mocks are injected).
```bash
python -m pytest tests/
```
