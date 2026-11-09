import json
import os
from pathlib import Path
from typing import Optional, Dict, Tuple
from scdm.domain.state import WorkflowState

def _load_company_dictionaries() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str]]:
    """
    Loads comprehensive mappings from the canonical dataset:
    id_to_name, id_to_country, id_to_industry, id_to_type.
    """
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    id_to_name = {}
    id_to_country = {}
    id_to_industry = {}
    id_to_type = {}
    
    for p in [
        base_dir / "all_unique_companies_and_codes.csv",
        base_dir / "output" / "canonical" / "all_unique_companies_and_codes.csv",
        base_dir / "output" / "canonical" / "canonical_companies.csv",
        base_dir / "dataset" / "canonical" / "canonical_companies.csv"
    ]:
        if p.exists():
            try:
                import pandas as pd
                df = pd.read_csv(p)
                id_col = 'Unique Company Code' if 'Unique Company Code' in df.columns else ('company_id' if 'company_id' in df.columns else df.columns[1])
                name_col = 'Company Name' if 'Company Name' in df.columns else ('company_name' if 'company_name' in df.columns else df.columns[0])
                country_col = 'Country / Region' if 'Country / Region' in df.columns else ('country_region' if 'country_region' in df.columns else None)
                industry_col = 'Industry Sector' if 'Industry Sector' in df.columns else ('industry' if 'industry' in df.columns else None)
                type_col = 'Company Type' if 'Company Type' in df.columns else ('company_type' if 'company_type' in df.columns else None)
                
                for _, row in df.iterrows():
                    cid = str(row[id_col]).strip()
                    cname = str(row[name_col]).strip() if pd.notna(row[name_col]) else f"Private Entity ({cid})"
                    if cname.lower() == 'nan' or not cname:
                        cname = f"Private Entity ({cid})"
                    id_to_name[cid] = cname
                    if country_col and pd.notna(row[country_col]):
                        id_to_country[cid] = str(row[country_col]).strip()
                    if industry_col and pd.notna(row[industry_col]):
                        id_to_industry[cid] = str(row[industry_col]).strip()
                    if type_col and pd.notna(row[type_col]):
                        id_to_type[cid] = str(row[type_col]).strip()
                break
            except Exception:
                pass
                
    return id_to_name, id_to_country, id_to_industry, id_to_type

def export_run_to_html(wf: WorkflowState, output_html_path: Optional[str] = None) -> str:
    """
    Exports a WorkflowState into an interactive, self-contained HTML visualizer
    with real listed company names, company codes, and multi-tier network topology.
    """
    if not output_html_path:
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        output_html_path = str(base_dir / "output" / "visualizer.html")
        
    out_path = Path(output_html_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    id_to_name, id_to_country, id_to_industry, id_to_type = _load_company_dictionaries()

    # 1. Prepare raw JSON string of the run state
    state_json = wf.model_dump_json(indent=2)
    
    # 2. Extract key display summaries
    focal_code = str(wf.focal_company_id or "Focal Entity")
    focal_name = id_to_name.get(focal_code, focal_code)
    query = wf.query or "Disruption Analysis"
    
    evt_desc = "No disruption event parsed"
    evt_mat = "N/A"
    evt_type = "UNKNOWN"
    if wf.disruption_events:
        e = wf.disruption_events[0]
        evt_desc = e.description
        evt_mat = e.affected_material or "General Supply Chain"
        evt_type = e.disruption_type

    # Format nodes & edges
    nodes_data = []
    edges_data = []
    if wf.visualization_payload:
        for n in wf.visualization_payload.nodes:
            nid = str(n.id)
            cname = id_to_name.get(nid, n.label or nid)
            # If label was already a clean name, keep it
            if n.label and n.label != nid:
                cname = n.label
            country = id_to_country.get(nid, "Not Specified")
            industry = id_to_industry.get(nid, "Not Specified")
            ctype = id_to_type.get(nid, "Not Specified")

            nodes_data.append({
                "id": nid,
                "code": nid,
                "name": cname,
                "label": cname,
                "tier": n.tier if n.tier is not None else 1,
                "is_focal": n.is_focal,
                "is_candidate": n.is_candidate,
                "risk_level": n.risk_level or "EVALUATED",
                "risk_score": n.risk_score if n.risk_score is not None else 0.0,
                "role": n.role or ("focal_company" if n.is_focal else "supplier"),
                "country": country,
                "industry": industry,
                "company_type": ctype
            })
        for e in wf.visualization_payload.edges:
            edges_data.append({
                "source": str(e.source),
                "target": str(e.target),
                "type": e.relationship_type,
                "is_disrupted": e.is_disrupted,
                "is_alternative": e.is_alternative
            })
            
    # Format paths
    paths_data = []
    for p in wf.impacted_paths:
        route_codes = [str(x) for x in p.ordered_path]
        route_names = [id_to_name.get(x, x) for x in route_codes]
        paths_data.append({
            "route_codes": route_codes,
            "route_names": route_names,
            "tier": p.distance if hasattr(p, "distance") else len(p.ordered_path) - 1
        })

    # Format risks
    risks_data = []
    for r in wf.risk_results:
        sup_id = str(r.supplier_id)
        sup_name = id_to_name.get(sup_id, sup_id)
        risks_data.append({
            "supplier_id": sup_id,
            "supplier_code": sup_id,
            "supplier_name": sup_name,
            "country": id_to_country.get(sup_id, "Not Specified"),
            "tier": r.tier,
            "score": r.score,
            "risk_level": r.risk_level,
            "reasons": r.reasons
        })

    # Format recommendations
    recs_data = []
    for rec in wf.recommendations:
        approval_val = "APPROVED"
        if wf.pending_approvals and rec.recommendation_id in wf.pending_approvals:
            approval_val = str(wf.pending_approvals[rec.recommendation_id].value if hasattr(wf.pending_approvals[rec.recommendation_id], "value") else wf.pending_approvals[rec.recommendation_id])
        target_id = str(rec.target_supplier_id)
        target_name = id_to_name.get(target_id, target_id)
        recs_data.append({
            "action": rec.action,
            "target_supplier_id": target_id,
            "target_supplier_name": target_name,
            "risk_context": rec.risk_context,
            "reasons": rec.reasons,
            "approval": approval_val
        })

    # Format alternatives
    alts_data = []
    for alt in wf.alternative_suppliers:
        cand_id = str(alt.candidate_id)
        cand_name = alt.candidate_name
        if not cand_name or cand_name == cand_id:
            cand_name = id_to_name.get(cand_id, cand_id)
        alts_data.append({
            "name": cand_name,
            "id": cand_id,
            "material": alt.product_or_material,
            "in_graph": alt.graph_presence,
            "score": alt.ranking_score,
            "status": alt.evidence_status.value if hasattr(alt.evidence_status, "value") else str(alt.evidence_status)
        })

    payload_package = {
        "focal": {
            "name": focal_name,
            "code": focal_code
        },
        "query": query,
        "event": {
            "type": evt_type,
            "material": evt_mat,
            "description": evt_desc
        },
        "nodes": nodes_data,
        "edges": edges_data,
        "paths": paths_data,
        "risks": risks_data,
        "recommendations": recs_data,
        "alternatives": alts_data,
        "counts": {
            "paths": len(paths_data),
            "nodes": len(nodes_data),
            "edges": len(edges_data),
            "risks": len(risks_data),
            "alts": len(alts_data)
        }
    }

    payload_json_str = json.dumps(payload_package)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SCDM Live Execution Visualizer - {focal_name}</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    .node-focal {{ fill: #3b82f6; stroke: #60a5fa; stroke-width: 3.5px; filter: drop-shadow(0 0 12px rgba(59,130,246,0.7)); }}
    .node-t1-high {{ fill: #ef4444; stroke: #f87171; stroke-width: 2.5px; filter: drop-shadow(0 0 10px rgba(239,68,68,0.6)); }}
    .node-t1-med {{ fill: #f97316; stroke: #fb923c; stroke-width: 2px; }}
    .node-t1-low {{ fill: #eab308; stroke: #facc15; stroke-width: 1.5px; }}
    .node-t2 {{ fill: #a855f7; stroke: #c084fc; stroke-width: 1.5px; }}
    .node-t3 {{ fill: #6366f1; stroke: #818cf8; stroke-width: 1.2px; }}
    .node-alt {{ fill: #10b981; stroke: #34d399; stroke-width: 2.5px; stroke-dasharray: 4 2; filter: drop-shadow(0 0 8px rgba(16,185,129,0.5)); }}
    
    .edge-supplies {{ stroke: #475569; stroke-width: 1.2px; stroke-opacity: 0.5; }}
    .edge-highlight {{ stroke: #38bdf8 !important; stroke-width: 3.5px !important; stroke-opacity: 1 !important; }}
    .edge-alt {{ stroke: #10b981; stroke-width: 2px; stroke-dasharray: 4 3; stroke-opacity: 0.8; }}
    
    .view-btn.active {{
      background: #2563eb;
      color: #ffffff;
      border-color: #3b82f6;
    }}
  </style>
</head>
<body class="bg-[#0b1120] text-[#f8fafc] antialiased min-h-screen p-4 md:p-6 flex flex-col font-sans">

  <!-- TOP HEADER -->
  <header class="max-w-7xl mx-auto w-full mb-6 border-b border-[#1e293b] pb-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
    <div>
      <div class="flex items-center gap-2">
        <span class="px-2.5 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          LIVE EXECUTION VISUALIZER
        </span>
        <span class="text-xs px-2.5 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono font-bold">
          Focal: {focal_name} (Code: {focal_code})
        </span>
      </div>
      <h1 class="text-2xl md:text-3xl font-extrabold tracking-tight mt-1 text-white">
        Supply Chain Network & Disruption Visualizer
      </h1>
      <p class="text-xs md:text-sm text-gray-400 mt-0.5">
        Disruption Query: <span class="text-cyan-300 font-medium">"{query}"</span>
      </p>
    </div>

    <!-- Live Execution Metrics Badges -->
    <div class="flex flex-wrap items-center gap-2 text-xs font-mono">
      <div class="p-2 rounded-lg bg-[#1e293b] border border-white/5 text-center min-w-[70px]">
        <span class="text-[10px] text-gray-400 block uppercase">Paths</span>
        <span class="font-bold text-white text-sm">{len(paths_data)}</span>
      </div>
      <div class="p-2 rounded-lg bg-[#1e293b] border border-white/5 text-center min-w-[70px]">
        <span class="text-[10px] text-gray-400 block uppercase">Nodes</span>
        <span class="font-bold text-cyan-400 text-sm">{len(nodes_data)}</span>
      </div>
      <div class="p-2 rounded-lg bg-[#1e293b] border border-white/5 text-center min-w-[70px]">
        <span class="text-[10px] text-gray-400 block uppercase">Edges</span>
        <span class="font-bold text-cyan-400 text-sm">{len(edges_data)}</span>
      </div>
      <div class="p-2 rounded-lg bg-[#1e293b] border border-white/5 text-center min-w-[70px]">
        <span class="text-[10px] text-gray-400 block uppercase">Risks</span>
        <span class="font-bold text-amber-400 text-sm">{len(risks_data)}</span>
      </div>
    </div>
  </header>

  <!-- NAVIGATION TABS -->
  <div class="max-w-7xl mx-auto w-full mb-6 flex items-center gap-2 border-b border-[#1e293b] pb-2 text-xs font-semibold">
    <button id="tab-network" onclick="switchView('network')" class="view-btn active px-4 py-2 rounded-lg border border-[#334155] transition-all flex items-center gap-2">
      <span>🌐</span>
      <span>Supply Chain Network ({len(nodes_data)} Companies)</span>
    </button>
    <button id="tab-risks" onclick="switchView('risks')" class="view-btn px-4 py-2 rounded-lg border border-[#334155] bg-[#1e293b] text-gray-400 transition-all flex items-center gap-2">
      <span>🎯</span>
      <span>Deterministic Risk Scores ({len(risks_data)} Suppliers)</span>
    </button>
    <button id="tab-paths" onclick="switchView('paths')" class="view-btn px-4 py-2 rounded-lg border border-[#334155] bg-[#1e293b] text-gray-400 transition-all flex items-center gap-2">
      <span>🌲</span>
      <span>Upstream Traversal Routes ({len(paths_data)})</span>
    </button>
    <button id="tab-raw" onclick="switchView('raw')" class="view-btn px-4 py-2 rounded-lg border border-[#334155] bg-[#1e293b] text-gray-400 transition-all flex items-center gap-2">
      <span>📋</span>
      <span>Raw WorkflowState JSON</span>
    </button>
  </div>

  <!-- VIEW 1: INTERACTIVE NETWORK CANVAS -->
  <section id="view-network" class="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-6 flex-grow">
    
    <!-- SVG Canvas (8 cols) -->
    <div class="lg:col-span-8 flex flex-col bg-[#131d31] border border-[#1e293b] rounded-2xl p-4 shadow-xl">
      <div class="flex items-center justify-between mb-3 border-b border-white/5 pb-2 text-xs font-medium">
        <div class="flex flex-wrap items-center gap-3">
          <span class="text-white font-bold flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-blue-500"></span> Focal Company</span>
          <span class="text-red-400 flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-red-500"></span> High Risk T1</span>
          <span class="text-orange-400 flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-orange-500"></span> Medium Risk T1</span>
          <span class="text-yellow-400 flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-yellow-500"></span> Low Risk T1</span>
          <span class="text-purple-400 flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-purple-500"></span> Tier 2</span>
          <span class="text-emerald-400 flex items-center gap-1.5"><span class="w-3 h-3 rounded-full bg-emerald-500"></span> Alternative</span>
        </div>

        <div class="flex items-center gap-2">
          <input type="text" id="search-input" onkeyup="filterNodes(this.value)" placeholder="Search company name or code..." class="bg-black/40 border border-white/10 text-xs px-2.5 py-1 rounded-lg text-white focus:outline-none focus:ring-1 focus:ring-blue-500 w-48">
          <button onclick="resetGraph()" class="px-2.5 py-1 rounded bg-black/40 hover:bg-black/60 text-xs font-mono text-gray-300 border border-white/10">
            Reset
          </button>
        </div>
      </div>

      <!-- SVG Container -->
      <div class="relative w-full h-[540px] bg-black/40 rounded-xl border border-white/5 overflow-hidden flex items-center justify-center">
        <svg id="network-svg" class="w-full h-full" viewBox="0 0 950 540">
          <defs>
            <marker id="arrow" viewBox="0 -5 10 10" refX="22" refY="0" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,-5L10,0L0,5" fill="#475569"/>
            </marker>
            <marker id="arrow-high" viewBox="0 -5 10 10" refX="22" refY="0" markerWidth="8" markerHeight="8" orient="auto">
              <path d="M0,-5L10,0L0,5" fill="#38bdf8"/>
            </marker>
          </defs>
          <g id="svg-edges"></g>
          <g id="svg-nodes"></g>
        </svg>
      </div>

      <div class="mt-2 text-[11px] text-gray-400 flex justify-between">
        <span>Click any node circle to inspect full company details and metrics.</span>
        <span class="font-mono text-cyan-300">Anchor: {focal_name} ({focal_code})</span>
      </div>
    </div>

    <!-- Node Inspector & Quick Actions (4 cols) -->
    <div class="lg:col-span-4 space-y-4 flex flex-col">
      <div class="bg-[#1e293b] border border-[#334155] rounded-2xl p-5 shadow-sm">
        <div class="flex items-center justify-between border-b border-[#334155] pb-3 mb-3">
          <div>
            <span id="insp-tier-tag" class="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 uppercase font-bold">
              Focal Anchor
            </span>
            <h3 id="insp-name" class="text-base font-bold text-white mt-1">
              {focal_name}
            </h3>
          </div>
          <span id="insp-pill" class="text-xs font-mono font-bold px-2 py-1 rounded bg-blue-500/20 text-blue-300">
            FOCAL ENTITY
          </span>
        </div>

        <div class="space-y-2 text-xs">
          <div class="flex justify-between py-1 border-b border-white/5">
            <span class="text-gray-400">Unique Company Code:</span>
            <span id="insp-code" class="font-mono font-bold text-cyan-300">{focal_code}</span>
          </div>
          <div class="flex justify-between py-1 border-b border-white/5">
            <span class="text-gray-400">Country / Region:</span>
            <span id="insp-country" class="font-sans text-gray-200">Not Specified</span>
          </div>
          <div class="flex justify-between py-1 border-b border-white/5">
            <span class="text-gray-400">Industry Sector:</span>
            <span id="insp-industry" class="font-sans text-gray-200">Automobiles & Components</span>
          </div>
          <div class="flex justify-between py-1 border-b border-white/5">
            <span class="text-gray-400">Network Tier:</span>
            <span id="insp-tier" class="font-mono text-gray-200">Tier 0 (Root)</span>
          </div>
          <div class="flex justify-between py-1 border-b border-white/5">
            <span class="text-gray-400">Deterministic Risk:</span>
            <span id="insp-risk" class="font-mono font-bold text-gray-200">N/A (Focal)</span>
          </div>
          <div class="flex justify-between py-1">
            <span class="text-gray-400">Role:</span>
            <span id="insp-role" class="text-cyan-400 font-semibold">Focal Company</span>
          </div>
        </div>
      </div>

      <!-- CSCO Strategy Card -->
      <div class="bg-[#1e293b] border border-[#334155] rounded-2xl p-5 shadow-sm flex-grow">
        <h4 class="text-xs font-bold uppercase text-white mb-2 flex items-center justify-between">
          <span>CSCO Action & Governance</span>
          <span class="text-[10px] px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">Agent 6 (LLM)</span>
        </h4>
        <div class="space-y-2 text-xs text-gray-300">
          <div class="p-2.5 rounded bg-black/40 border border-white/5">
            <span class="text-[10px] uppercase text-gray-400 block mb-0.5">Proposed Action</span>
            <span class="font-bold text-white text-sm">{recs_data[0]["action"] if recs_data else "ALTERNATIVE_SOURCING"}</span>
          </div>
          <div class="p-2.5 rounded bg-black/40 border border-white/5">
            <span class="text-[10px] uppercase text-gray-400 block mb-0.5">Target Supplier</span>
            <span class="font-sans font-bold text-white block">{recs_data[0]["target_supplier_name"] if recs_data else (risks_data[0]["supplier_name"] if risks_data else "N/A")}</span>
            <span class="font-mono text-cyan-300 text-[11px]">Code: {recs_data[0]["target_supplier_id"] if recs_data else (risks_data[0]["supplier_code"] if risks_data else "N/A")}</span>
          </div>
          <div class="p-2.5 rounded bg-black/40 border border-white/5 flex justify-between items-center">
            <span class="text-gray-400">Approval State:</span>
            <span class="font-bold text-emerald-400 font-mono">{recs_data[0]["approval"] if recs_data else "APPROVED"}</span>
          </div>
        </div>
      </div>
    </div>

  </section>

  <!-- VIEW 2: RISK BREAKDOWN -->
  <section id="view-risks" class="max-w-7xl mx-auto w-full hidden">
    <div class="bg-[#1e293b] border border-[#334155] rounded-2xl p-6 shadow-sm">
      <div class="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
        <div>
          <h3 class="text-base font-bold text-white">Topological Risk Score Table (Listed Company Names & Unique Codes)</h3>
          <p class="text-xs text-gray-400">Evaluated deterministically across graph paths using the 5-factor topological formula.</p>
        </div>
        <span class="text-xs font-mono px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 font-bold">
          {len(risks_data)} Scored Suppliers
        </span>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="border-b border-white/10 text-gray-400 uppercase font-mono text-[10px]">
              <th class="py-2.5 px-3">Listed Company Name</th>
              <th class="py-2.5 px-3">Unique Company Code</th>
              <th class="py-2.5 px-3">Tier</th>
              <th class="py-2.5 px-3">Risk Score</th>
              <th class="py-2.5 px-3">Risk Level</th>
              <th class="py-2.5 px-3">Topological Reasons</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-white/5">
            {"".join([f'''
            <tr class="hover:bg-white/5 transition-colors">
              <td class="py-2.5 px-3 font-bold text-white font-sans">{r["supplier_name"]}</td>
              <td class="py-2.5 px-3 font-mono text-cyan-300 font-bold">{r["supplier_code"]}</td>
              <td class="py-2.5 px-3 text-gray-300 font-mono">Tier {r["tier"]}</td>
              <td class="py-2.5 px-3 font-bold text-cyan-300 font-mono">{r["score"]:.2f} / 1.00</td>
              <td class="py-2.5 px-3 font-mono">
                <span class="px-2 py-0.5 rounded text-[10px] font-bold {'bg-red-500/20 text-red-300' if r['risk_level']=='HIGH' else ('bg-orange-500/20 text-orange-300' if r['risk_level']=='MEDIUM' else 'bg-yellow-500/20 text-yellow-300')}">
                  {r["risk_level"]}
                </span>
              </td>
              <td class="py-2.5 px-3 font-sans text-gray-300">{("; ".join(r["reasons"]) if r.get("reasons") else "Topological path concentration.")}</td>
            </tr>
            ''' for r in risks_data])}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- VIEW 3: PATHS LIST -->
  <section id="view-paths" class="max-w-7xl mx-auto w-full hidden">
    <div class="bg-[#1e293b] border border-[#334155] rounded-2xl p-6 shadow-sm">
      <div class="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
        <div>
          <h3 class="text-base font-bold text-white">Traversed Upstream Supply Routes (Company Names & Unique Codes)</h3>
          <p class="text-xs text-gray-400">Full path chains traced from upstream suppliers into {focal_name} (Code: {focal_code}).</p>
        </div>
        <span class="text-xs font-mono px-2.5 py-1 rounded bg-blue-500/20 text-blue-300 font-bold">
          {len(paths_data)} Total Paths
        </span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[600px] overflow-y-auto pr-2 text-xs">
        {"".join([f'''
        <div class="p-3 rounded-xl bg-black/40 border border-white/5 space-y-1">
          <div class="flex justify-between items-center text-[10px] font-mono text-gray-400 mb-1">
            <span class="text-cyan-400 font-bold">Path #{i+1}</span>
            <span>Distance: Tier {p["tier"]}</span>
          </div>
          <div class="text-gray-200 font-sans break-words leading-relaxed">
            {" ──► ".join([f'<span class="font-semibold text-white">{name}</span> <span class="text-[10px] text-gray-400 font-mono">({code})</span>' for name, code in zip(p["route_names"], p["route_codes"])])}
          </div>
        </div>
        ''' for i, p in enumerate(paths_data)])}
      </div>
    </div>
  </section>

  <!-- VIEW 4: RAW WORKFLOWSTATE JSON -->
  <section id="view-raw" class="max-w-7xl mx-auto w-full hidden">
    <div class="bg-[#1e293b] border border-[#334155] rounded-2xl p-6 shadow-sm">
      <h3 class="text-base font-bold text-white mb-2">Complete Serialized WorkflowState JSON</h3>
      <pre class="p-4 rounded-xl bg-black/60 text-gray-300 font-mono text-xs overflow-x-auto max-h-[600px] border border-white/5">{state_json}</pre>
    </div>
  </section>

  <!-- DATA & LOGIC SCRIPT -->
  <script>
    const RUN_DATA = {payload_json_str};

    function switchView(name) {{
      ['network', 'risks', 'paths', 'raw'].forEach(v => {{
        document.getElementById(`view-${{v}}`).classList.add('hidden');
        document.getElementById(`tab-${{v}}`).classList.remove('active');
      }});
      document.getElementById(`view-${{name}}`).classList.remove('hidden');
      document.getElementById(`tab-${{name}}`).classList.add('active');
    }}

    function renderGraph(filterText = '') {{
      const svgNodes = document.getElementById('svg-nodes');
      const svgEdges = document.getElementById('svg-edges');
      svgNodes.innerHTML = '';
      svgEdges.innerHTML = '';

      const width = 950;
      const height = 540;
      const cx = width / 2;
      const cy = height / 2;

      // Filter nodes if search query present
      let displayNodes = RUN_DATA.nodes;
      if (filterText.trim()) {{
        const ft = filterText.toLowerCase();
        displayNodes = displayNodes.filter(n => 
          (n.name || '').toLowerCase().includes(ft) ||
          (n.code || '').toLowerCase().includes(ft) ||
          n.is_focal
        );
      }}

      // Limit dense rendering to 75 primary nodes on canvas for performance/clarity
      const visibleSet = new Set(displayNodes.slice(0, 75).map(n => n.id));
      visibleSet.add(RUN_DATA.focal.code);

      const posMap = {{}};
      posMap[RUN_DATA.focal.code] = {{ x: cx, y: cy }};

      const t1 = displayNodes.filter(n => n.tier === 1 && !n.is_focal && visibleSet.has(n.id));
      const t2 = displayNodes.filter(n => n.tier === 2 && visibleSet.has(n.id));
      const t3 = displayNodes.filter(n => n.tier >= 3 && visibleSet.has(n.id));
      const alt = displayNodes.filter(n => n.is_candidate && visibleSet.has(n.id));

      // Radial positioning
      t1.forEach((n, i) => {{
        const angle = (i / Math.max(1, t1.length)) * 2 * Math.PI;
        posMap[n.id] = {{ x: cx + 155 * Math.cos(angle), y: cy + 155 * Math.sin(angle) }};
      }});

      t2.forEach((n, i) => {{
        const angle = (i / Math.max(1, t2.length)) * 2 * Math.PI + 0.2;
        posMap[n.id] = {{ x: cx + 235 * Math.cos(angle), y: cy + 235 * Math.sin(angle) }};
      }});

      t3.forEach((n, i) => {{
        const angle = (i / Math.max(1, t3.length)) * 2 * Math.PI + 0.4;
        posMap[n.id] = {{ x: cx + 290 * Math.cos(angle), y: cy + 290 * Math.sin(angle) }};
      }});

      alt.forEach((n, i) => {{
        posMap[n.id] = {{ x: cx - 220 + (i * 90), y: cy + 200 }};
      }});

      // Render Edges
      RUN_DATA.edges.forEach(e => {{
        const p1 = posMap[e.source];
        const p2 = posMap[e.target];
        if (!p1 || !p2) return;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', p1.x);
        line.setAttribute('y1', p1.y);
        line.setAttribute('x2', p2.x);
        line.setAttribute('y2', p2.y);
        line.setAttribute('class', e.is_alternative ? 'edge-alt' : 'edge-supplies');
        line.setAttribute('marker-end', 'url(#arrow)');
        svgEdges.appendChild(line);
      }});

      // Render Nodes
      displayNodes.forEach(n => {{
        const p = posMap[n.id];
        if (!p) return;

        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', 'cursor-pointer');
        g.onclick = () => selectNode(n);

        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', p.x);
        circle.setAttribute('cy', p.y);

        let r = 11;
        let cls = 'node-t2';
        if (n.is_focal) {{
          r = 21;
          cls = 'node-focal';
        }} else if (n.is_candidate) {{
          r = 13;
          cls = 'node-alt';
        }} else if (n.tier === 1) {{
          r = 14;
          if (n.risk_score >= 0.7) cls = 'node-t1-high';
          else if (n.risk_score >= 0.4) cls = 'node-t1-med';
          else cls = 'node-t1-low';
        }} else if (n.tier >= 3) {{
          r = 8;
          cls = 'node-t3';
        }}

        circle.setAttribute('r', r);
        circle.setAttribute('class', cls);

        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', p.x);
        text.setAttribute('y', p.y + r + 12);
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('fill', '#e2e8f0');
        text.setAttribute('font-size', n.is_focal ? '12px' : '9px');
        text.setAttribute('font-weight', n.is_focal ? 'bold' : 'normal');
        
        // Show clean company name
        const displayName = (n.name || n.label || n.id);
        text.textContent = displayName.length > 17 ? displayName.substring(0, 15) + '..' : displayName;

        g.appendChild(circle);
        g.appendChild(text);
        svgNodes.appendChild(g);
      }});
    }}

    function selectNode(n) {{
      const compName = n.name || n.label || n.id;
      const compCode = n.code || n.id;
      
      document.getElementById('insp-name').innerText = compName;
      document.getElementById('insp-code').innerText = compCode;
      document.getElementById('insp-country').innerText = n.country || "Not Specified";
      document.getElementById('insp-industry').innerText = n.industry || "Not Specified";
      document.getElementById('insp-tier').innerText = n.is_focal ? "Tier 0 (Root)" : `Tier ${{n.tier || 1}}`;
      document.getElementById('insp-tier-tag').innerText = n.is_focal ? "Focal Anchor" : `Tier ${{n.tier || 1}} Supplier`;
      
      const score = n.risk_score !== undefined && !n.is_focal ? `${{n.risk_score.toFixed(2)}} / 1.00` : "N/A";
      document.getElementById('insp-risk').innerText = score;

      const pill = document.getElementById('insp-pill');
      if (n.is_focal) {{
        pill.innerText = "FOCAL ENTITY";
        pill.className = "text-xs font-mono font-bold px-2 py-1 rounded bg-blue-500/20 text-blue-300";
      }} else if (n.risk_score >= 0.7) {{
        pill.innerText = "HIGH RISK";
        pill.className = "text-xs font-mono font-bold px-2 py-1 rounded bg-red-500/20 text-red-300";
      }} else if (n.risk_score >= 0.4) {{
        pill.innerText = "MEDIUM RISK";
        pill.className = "text-xs font-mono font-bold px-2 py-1 rounded bg-orange-500/20 text-orange-300";
      }} else {{
        pill.innerText = "LOW RISK";
        pill.className = "text-xs font-mono font-bold px-2 py-1 rounded bg-yellow-500/20 text-yellow-300";
      }}
    }}

    function filterNodes(val) {{
      renderGraph(val);
    }}

    function resetGraph() {{
      document.getElementById('search-input').value = '';
      renderGraph();
    }}

    // Initial render
    renderGraph();
  </script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    return str(out_path)
