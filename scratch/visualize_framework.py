#!/usr/bin/env python3
"""
SCDM Framework & Supply Chain Network Visualizer
------------------------------------------------
Visualizes both:
1. The entire 7-agent multi-agent framework architecture & step-by-step working.
2. The complete supply chain network traversal, risk scores, and alternative sourcing
   from the most recent demo run (or canonical dataset).
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Terminal Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
DIM = "\033[2m"
RESET = "\033[0m"

def print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")

def print_step(step_num: int, name: str, agent: str, layer: str, desc: str):
    layer_color = MAGENTA if "LLM" in layer else GREEN if "Graph" in layer or "Deterministic" in layer else YELLOW
    print(f"{BOLD}{BLUE}[Step {step_num}/10]{RESET} {BOLD}{name}{RESET}")
    print(f"  • {BOLD}Component / Agent:{RESET} {CYAN}{agent}{RESET}")
    print(f"  • {BOLD}System Layer:{RESET}      {layer_color}{layer}{RESET}")
    print(f"  • {BOLD}Operation:{RESET}         {desc}")
    print(f"{CYAN}{'-'*80}{RESET}")

def visualize_architecture():
    print_header("1. SCDM TOP-TO-BOTTOM ARCHITECTURAL MAP")
    
    arch_ascii = f"""
{BOLD}{CYAN}                      ┌─────────────────────────────────────────┐
                      │        USER INPUT / SCENARIO TRIGGER     │
                      │  • Focal Company: 'Ford Motor Co'       │
                      │  • Query: 'Shortage of Palladium'       │
                      └────────────────────┬────────────────────┘{RESET}
                                           │
                                           ▼
{BOLD}{MAGENTA}┌──────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: UNSTRUCTURED WEB & LLM INTERPRETATION (Probabilistic Layer)        │
│                                                                              │
│  [DuckDuckGo Provider]         ───> Real-time web news retrieval             │
│  [Agent 1: Disruption Monitor] ───> Extracts DisruptionEvent (Material, Region)│
│  [Agent 3: Product Search]     ───> Grounded evidence web search (Zero-BOM) │
└──────────────────────────────────────────┬───────────────────────────────────┘{RESET}
                                           │ DisruptionEvent + ProductClaims
                                           ▼
{BOLD}{GREEN}┌──────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: DETERMINISTIC ENTERPRISE GRAPH FACTS (Neo4j Mathematical Engine)    │
│                                                                              │
│  [Agent 2a: Entity Resolution] ───> Exact / Normalized String Match to ID    │
│  [Agent 2b: Graph Traversal]   ───> Traverses N-tier paths (SUPPLIES/SELLS_TO)│
│  [Agent 5: Risk Engine]        ───> 5-Factor Deterministic Topological Score │
└──────────────────────────────────────────┬───────────────────────────────────┘{RESET}
                                           │ Topologically Ranked RiskResults
                                           ▼
{BOLD}{MAGENTA}┌──────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: EXECUTIVE REASONING & STRATEGY                                      │
│                                                                              │
│  [Agent 6: CSCO Decision Agent]───> Synthesizes Risk into Recommendations    │
└──────────────────────────────────────────┬───────────────────────────────────┘{RESET}
                                           │ Recommendation Pending Approval
                                           ▼
{BOLD}{YELLOW}╔══════════════════════════════════════════════════════════════════════════════╗
║  HUMAN-IN-THE-LOOP APPROVAL GATE (Security / Autonomy Checkpoint)            ║
║  "Authorize alternative sourcing search for critical exposed suppliers?"    ║
║  Options: [APPROVED] ──> Proceed to Agent 7  |  [REJECTED] ──> Skip to Viz   ║
╚══════════════════════════════════════════╤═══════════════════════════════════╝{RESET}
                                           │ If Approved
                                           ▼
{BOLD}{BLUE}┌──────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: QUALIFIED SOURCING & SYNTHESIS                                     │
│                                                                              │
│  [Agent 7: Alternative Sourcing]───> External Discovery + Graph Connectivity │
│  [Agent 4: Network Visualizer]  ───> Subgraph Topology Serialization        │
│  [Executive Briefing Report]    ───> High-level Terminal & Markdown Summary  │
└──────────────────────────────────────────────────────────────────────────────┘{RESET}
"""
    print(arch_ascii)

def simulate_step_by_step():
    print_header("2. AGENT PIPELINE SIMULATION (STEP-BY-STEP TRACE)")
    
    from scdm.domain.state import WorkflowState
    from scdm.domain.constants import ApprovalState, DataLayer
    from scdm.domain.schemas import DisruptionEvent, ExposureResult, SupplierPath, RiskResult, Recommendation, AlternativeSupplier
    from scdm.workflow.graph import WorkflowBuilder, GraphState
    from scdm.__main__ import MockLLMClient, MockDDGProvider, MockResolver, MockTraversal, MockRiskEngine
    
    llm = MockLLMClient()
    ddg = MockDDGProvider()
    resolver = MockResolver()
    traversal = MockTraversal()
    risk_engine = MockRiskEngine()
    
    def auto_approve(wf):
        print(f"  {YELLOW}>>> [HUMAN GATE]: Action automatically APPROVED for simulation!{RESET}")
        for rec in wf.recommendations:
            wf.pending_approvals[rec.recommendation_id] = ApprovalState.APPROVED
            
    builder = WorkflowBuilder(llm, ddg, resolver, traversal, risk_engine, approval_callback=auto_approve)
    
    initial_state = GraphState(workflow_state=WorkflowState(
        query="Severe shortage of Palladium affecting catalytic converters",
        focal_company_id="Ford Motor"
    ))
    wf = initial_state["workflow_state"]
    
    # 1
    print_step(1, "Retrieve External Evidence", "DuckDuckGo Provider", "External Search Layer",
               "Queries DuckDuckGo search API to gather reliable news articles and market snippets.")
    wf.gathered_evidence = ddg.search(wf.query)
    print(f"    {GREEN}✓ Gathered {len(wf.gathered_evidence)} verified evidence sources.{RESET}\n")

    # 2
    print_step(2, "Disruption Understanding", "Agent 1: DisruptionMonitorAgent", "LLM Interpretation (Gemini)",
               "Extracts structured DisruptionEvent: material, severity, geography, and event classification.")
    event = builder.monitor_agent.extract_event(wf.query, wf.gathered_evidence)
    wf.disruption_events.append(event)
    print(f"    {GREEN}✓ Disruption Event Parsed:{RESET} Type={BOLD}{event.disruption_type}{RESET}, Material={BOLD}{event.affected_material}{RESET}\n")

    # 3
    print_step(3, "Evidence-Grounded Product Search", "Agent 3: ProductSearchAgent", "LLM + External Search",
               "Finds external evidence connecting suppliers to the disrupted material (zero BOM hallucination).")
    claims = builder.product_agent.search_product_context(event.affected_material)
    wf.product_claims.extend(claims)
    print(f"    {GREEN}✓ Grounded Claims Extracted:{RESET} {len(claims)} candidate claims linked to '{event.affected_material}'\n")

    # 4
    print_step(4, "Supply-Chain Entity Resolution", "Agent 2a: EntityResolver", "Deterministic Graph Layer",
               "Resolves natural language input 'Ford Motor' into canonical Neo4j Company ID.")
    res = resolver.resolve_focal_company(wf.focal_company_id)
    wf.focal_company_id = res.resolved_company_id
    print(f"    {GREEN}✓ Canonical Resolution:{RESET} 'Ford Motor' -> {BOLD}{res.resolved_company_id}{RESET} ({res.status.value})\n")

    # 5
    print_step(5, "Graph Traversal (Multi-Tier Upstream)", "Agent 2b: GraphTraversal", "Deterministic Graph Layer (Cypher)",
               "Queries Neo4j graph for all Tier 1, Tier 2, and Tier 3 upstream paths connecting to focal company.")
    exposure = traversal.get_upstream_exposure(wf.focal_company_id, max_depth=3)
    wf.impacted_paths = exposure.paths
    print(f"    {GREEN}✓ Graph Traversal Complete:{RESET} {exposure.path_count} paths, Max Depth=Tier {exposure.max_depth_observed}\n")

    # 6
    print_step(6, "Topological Risk Calculation", "Agent 5: RiskEngine", "Deterministic Calculation (No LLM)",
               "Applies 5-factor mathematical formula: Breadth (35%) + Concentration (25%) + Proximity (20%) + Centrality (10%) + Depth (10%).")
    rrs = risk_engine.calculate_risk(exposure)
    wf.risk_results.extend(rrs)
    top_risk = rrs[0]
    print(f"    {GREEN}✓ Deterministic Risk Computed:{RESET} Supplier {BOLD}{top_risk.supplier_id}{RESET} -> Score={RED}{top_risk.score:.2f}{RESET} ({top_risk.risk_level})\n")

    # 7
    print_step(7, "Executive Decision Formulation", "Agent 6: CSCO Decision Agent", "LLM Strategy Layer",
               "Chief Supply Chain Officer agent translates numerical graph risk into a concrete operational recommendation.")
    rec = builder.csco_agent.generate_recommendation(top_risk, event, wf.gathered_evidence)
    wf.recommendations.append(rec)
    wf.pending_approvals[rec.recommendation_id] = ApprovalState.PENDING
    print(f"    {GREEN}✓ Executive Recommendation Formulated:{RESET} Action={BOLD}{rec.action}{RESET} for {rec.target_supplier_id}\n")

    # 8
    print_step(8, "Human-In-The-Loop Approval Boundary", "Security Gate / Governance", "Human Authorization",
               "Enforces a synchronous pause. Automated sourcing cannot proceed without authorized decision.")
    auto_approve(wf)
    print(f"    {GREEN}✓ Approval Gate Cleared:{RESET} Status = {GREEN}{ApprovalState.APPROVED.value}{RESET}\n")

    # 9
    print_step(9, "Qualified Alternative Sourcing", "Agent 7: AlternativeSourcingAgent", "Hybrid (Web Search + Graph Fact)",
               "Discovers candidate replacement suppliers and validates whether they are connected in the canonical graph.")
    candidates = builder.sourcing_agent.extract_and_qualify_candidates(
        material=event.affected_material,
        disruption_desc=event.description,
        evidence=wf.gathered_evidence,
        focal_company_id=wf.focal_company_id
    )
    wf.alternative_suppliers.extend(candidates)
    alt = candidates[0]
    print(f"    {GREEN}✓ Alternative Sourcing Qualified:{RESET} {BOLD}{alt.candidate_name}{RESET} (In Graph: {alt.graph_presence}, Score: {alt.ranking_score:.2f})\n")

    # 10
    print_step(10, "Network Visualization & Executive Reporting", "Agent 4 & Reporting Engine", "Serialization & Presentation",
               "Compiles serialized graph payload for UI rendering and outputs executive terminal briefing.")
    payload = builder.visualizer_agent.generate_visualization(
        focal_company_id=wf.focal_company_id,
        impacted_paths=wf.impacted_paths,
        risk_results=wf.risk_results,
        alternative_suppliers=wf.alternative_suppliers,
        disrupted_supplier_ids=[event.event_id]
    )
    wf.visualization_payload = payload
    print(f"    {GREEN}✓ Visualization Payload Compiled:{RESET} {len(payload.nodes)} nodes, {len(payload.edges)} edges\n")

def _load_company_map(base_dir: Path):
    dict_file = base_dir / "all_unique_companies_and_codes.csv"
    id_to_name = {}
    if dict_file.exists():
        try:
            import pandas as pd
            df = pd.read_csv(dict_file)
            for _, r in df.iterrows():
                id_to_name[str(r["Unique Company Code"]).strip()] = str(r["Company Name"]).strip()
        except Exception:
            pass
    return id_to_name

def display_latest_demo_run(run_file_path=None):
    base_dir = Path(__file__).resolve().parent.parent
    if not run_file_path:
        run_file_path = base_dir / "output" / "latest_run.json"
    else:
        run_file_path = Path(run_file_path)
        
    print_header("3. SUPPLY CHAIN NETWORK & TRAVERSAL OUTPUT (LATEST DEMO RUN)")
    
    if not run_file_path.exists():
        print(f"{YELLOW}No recorded demo run found at {run_file_path}.{RESET}")
        print(f"Run a demo using:\n  {CYAN}python -m scdm --focal-company 'Ford Motor' --query 'Shortage of Palladium' --mode MOCK{RESET}\n")
        return

    try:
        with open(run_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"{RED}Error reading run file: {e}{RESET}")
        return

    id_to_name = _load_company_map(base_dir)

    def format_entity(cid):
        s_id = str(cid).strip()
        name = id_to_name.get(s_id)
        if name and name != s_id:
            return f"{name} ({s_id})"
        return s_id

    # Extract high level run info
    query = data.get("query", "Unknown Query")
    focal_id = data.get("focal_company_id", "Unknown")
    focal_display = format_entity(focal_id)
    events = data.get("disruption_events", [])
    paths = data.get("impacted_paths", [])
    risks = data.get("risk_results", [])
    recs = data.get("recommendations", [])
    alts = data.get("alternative_suppliers", [])
    viz = data.get("visualization_payload", {})
    nodes = viz.get("nodes", []) if isinstance(viz, dict) else []
    edges = viz.get("edges", []) if isinstance(viz, dict) else []

    print(f"{BOLD}Scenario Query:{RESET}        {CYAN}{query}{RESET}")
    print(f"{BOLD}Focal Company Anchor:{RESET}  {GREEN}{focal_display}{RESET}")
    if events:
        evt = events[0]
        print(f"{BOLD}Disruption Detected:{RESET}   {RED}{evt.get('disruption_type')} - {evt.get('affected_material')}{RESET}")
        print(f"{BOLD}Event Description:{RESET}     {evt.get('description')}")
    print(f"{CYAN}{'-'*80}{RESET}")

    # Display Traversal Network Statistics
    print(f"\n{BOLD}{CYAN}🌐 SUPPLY CHAIN TOPOLOGY & TRAVERSAL SUMMARY{RESET}")
    print(f"  • {BOLD}Total Upstream Paths Found:{RESET} {len(paths)}")
    print(f"  • {BOLD}Visual Network Nodes:{RESET}       {len(nodes)}")
    print(f"  • {BOLD}Visual Network Edges:{RESET}       {len(edges)}")
    print(f"  • {BOLD}Scored Exposed Suppliers:{RESET}   {len(risks)}")
    print(f"  • {BOLD}Qualified Alternatives:{RESET}     {len(alts)}")

    # Display Upstream Paths Tree
    print(f"\n{BOLD}{CYAN}🌲 UPSTREAM MULTI-TIER TRAVERSAL TREE{RESET}")
    
    tier_1_paths = [p for p in paths if len(p.get("ordered_path", [])) == 2]
    tier_2_paths = [p for p in paths if len(p.get("ordered_path", [])) == 3]
    tier_3_paths = [p for p in paths if len(p.get("ordered_path", [])) >= 4]

    print(f"  {BOLD}Tier 1 Paths ({len(tier_1_paths)} direct routes):{RESET}")
    for p in tier_1_paths[:6]:
        route = " ──[SUPPLIES]──► ".join([format_entity(x) for x in p.get("ordered_path", [])])
        print(f"    • {route}")
    if len(tier_1_paths) > 6:
        print(f"    {DIM}... and {len(tier_1_paths) - 6} more Tier 1 paths{RESET}")

    if tier_2_paths:
        print(f"\n  {BOLD}Tier 2 Paths ({len(tier_2_paths)} secondary routes):{RESET}")
        for p in tier_2_paths[:6]:
            route = " ──► ".join([format_entity(x) for x in p.get("ordered_path", [])])
            print(f"    • {route}")
        if len(tier_2_paths) > 6:
            print(f"    {DIM}... and {len(tier_2_paths) - 6} more Tier 2 paths{RESET}")

    if tier_3_paths:
        print(f"\n  {BOLD}Tier 3 Paths ({len(tier_3_paths)} deep tier routes):{RESET}")
        for p in tier_3_paths[:4]:
            route = " ──► ".join([format_entity(x) for x in p.get("ordered_path", [])])
            print(f"    • {route}")
        if len(tier_3_paths) > 4:
            print(f"    {DIM}... and {len(tier_3_paths) - 4} more Tier 3 paths{RESET}")

    # Display Top Risk-Scored Suppliers
    print(f"\n{BOLD}{CYAN}🎯 DETERMINISTIC RISK SCORES (TOP EXPOSED SUPPLIERS){RESET}")
    print(f"{'Company Name & Code':<48} | {'Tier':<6} | {'Risk Score':<12} | {'Risk Level'}")
    print("-" * 80)
    for r in sorted(risks, key=lambda x: x.get("score", 0), reverse=True)[:8]:
        sup_raw = str(r.get("supplier_id", "Unknown"))
        sup_formatted = format_entity(sup_raw)[:46]
        tier = f"Tier {r.get('tier', 1)}"
        score = f"{r.get('score', 0):.2f} / 1.00"
        lvl = r.get("risk_level", "UNKNOWN")
        lvl_color = RED if lvl == "HIGH" else (YELLOW if lvl == "MEDIUM" else GREEN)
        print(f"{sup_formatted:<48} | {tier:<6} | {score:<12} | {lvl_color}{lvl}{RESET}")

    # Recommendations & Alternatives
    if recs:
        print(f"\n{BOLD}{CYAN}📋 CSCO MITIGATION RECOMMENDATION{RESET}")
        rec = recs[0]
        target_display = format_entity(rec.get('target_supplier_id'))
        print(f"  • {BOLD}Action:{RESET}        {BOLD}{rec.get('action')}{RESET}")
        print(f"  • {BOLD}Target Supplier:{RESET} {target_display}")
        print(f"  • {BOLD}Strategic Risk:{RESET}  {rec.get('risk_context')}")
        print(f"  • {BOLD}Approval State:{RESET} {GREEN}{data.get('pending_approvals', {}).get(rec.get('recommendation_id'), 'PENDING')}{RESET}")

    if alts:
        print(f"\n{BOLD}{CYAN}🚀 QUALIFIED ALTERNATIVE SUPPLIERS (GRAPH VALIDATED){RESET}")
        for a in alts:
            name = a.get("candidate_name", "Candidate")
            in_graph = a.get("graph_presence", False)
            score = a.get("ranking_score", 0.0)
            status = a.get("evidence_status", "UNVERIFIED")
            print(f"  • {BOLD}{name}{RESET} (Score: {score:.2f}) | In Canonical Graph: {GREEN if in_graph else RED}{in_graph}{RESET} | Status: {status}")

    print(f"\n{GREEN}✓ Active run output successfully rendered from {run_file_path}{RESET}")

def main():
    parser = argparse.ArgumentParser(description="SCDM Framework & Network Visualizer")
    parser.add_argument("--run", type=str, default="latest", help="Path to run JSON file, or 'latest'")
    parser.add_argument("--skip-sim", action="store_true", help="Skip the step-by-step agent simulation")
    args = parser.parse_args()

    visualize_architecture()
    
    if not args.skip_sim:
        simulate_step_by_step()
        
    display_latest_demo_run(None if args.run == "latest" else args.run)
    
    print_header("VISUALIZATION RUN COMPLETE")
    print(f"{GREEN}✓ The complete framework, agent lifecycle, and latest run network have been visualized.{RESET}")
    print(f"{CYAN}✓ Open the interactive HTML dashboard to explore the dynamic force-directed graph.{RESET}\n")

if __name__ == "__main__":
    main()
