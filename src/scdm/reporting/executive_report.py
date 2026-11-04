import logging
from typing import List, Optional
from scdm.domain.state import WorkflowState
from scdm.domain.constants import ApprovalState, EvidenceStatus

logger = logging.getLogger(__name__)

def render_cli_report(state: WorkflowState) -> str:
    """
    Renders a deterministic, human-readable CSCO executive report.
    Clearly distinguishes factual graph data, external evidence, and LLM interpretation.
    """
    lines = []
    lines.append("\n" + "="*80)
    lines.append("CSCO EXECUTIVE REPORT")
    lines.append("="*80)
    
    # 1. DISRUPTION SUMMARY
    lines.append("\n[LLM_INTERPRETATION] DISRUPTION SUMMARY")
    if state.disruption_events:
        for d in state.disruption_events:
            lines.append(f"- Type: {d.disruption_type}")
            lines.append(f"- Desc: {d.description}")
            if d.affected_material:
                lines.append(f"- Material: {d.affected_material}")
            if d.location:
                lines.append(f"- Location: {d.location}")
            lines.append(f"  (Confidence: {d.confidence})")
    else:
        lines.append("- UNKNOWN / NO DISRUPTION EVENT")

    # 2. EVIDENCE & SOURCES
    lines.append("\n[EXTERNAL_EVIDENCE] RETRIEVED SOURCES")
    if state.gathered_evidence:
        for ev in state.gathered_evidence:
            status_name = getattr(ev.status, "name", str(ev.status))
            lines.append(f"- {ev.title or 'Unknown Title'}")
            lines.append(f"  URL: {ev.source_url or 'Unknown'}")
            lines.append(f"  Status: {status_name}")
    else:
        lines.append("- NO EXTERNAL EVIDENCE RETRIEVED")

    # 3. PRODUCT CONTEXT
    lines.append("\n[LLM_INTERPRETATION] EVIDENCE-BACKED PRODUCT CONTEXT")
    if state.product_claims:
        for claim in state.product_claims:
            lines.append(f"- {claim.subject_name} -> {claim.predicate} -> {claim.object_value}")
            source = claim.sources[0].source_url if claim.sources else 'Unknown'
            lines.append(f"  Source: {source}")
            lines.append(f"  State: {claim.status.value}")
            lines.append(f"  {claim.uncertainty}")
    else:
        lines.append("- UNKNOWN / NO PRODUCT CLAIMS")

    # 4. RESOLVED FOCAL COMPANY
    lines.append("\n[GRAPH_FACT] FOCAL COMPANY")
    if state.focal_company_id:
        lines.append(f"- ID: {state.focal_company_id}")
    else:
        lines.append("- UNRESOLVED")

    # 5. MULTI-TIER EXPOSURE
    lines.append("\n[GRAPH_FACT] MULTI-TIER EXPOSURE")
    if state.impacted_paths:
        lines.append(f"- {len(state.impacted_paths)} supply paths identified.")
    elif not state.focal_company_id:
        lines.append("- EXPOSURE UNKNOWN (Focal company not resolved)")
    elif state.errors:
        lines.append("- EXPOSURE UNKNOWN (Workflow errors occurred)")
    else:
        lines.append("- NO EXPOSURE PATHS FOUND IN CURRENT GRAPH (Valid query, 0 paths)")
        
    # Workflow Errors
    if state.errors:
        lines.append("\n[WORKFLOW_ERROR] EXCEPTIONS / ISSUES")
        for err in state.errors:
            lines.append(f"- {err}")

    # 6 & 7. RISK ASSESSMENT
    lines.append("\n[DETERMINISTIC_CALCULATION] RISK EXPOSURE")
    if state.risk_results:
        for r in state.risk_results:
            lines.append(f"- Supplier {r.supplier_id} (Tier {r.tier})")
            lines.append(f"  Score: {r.score:.2f} | Level: {r.risk_level}")
            if r.reasons:
                lines.append(f"  Reason: {r.reasons[0]}")
    else:
        lines.append("- NO RISK RESULTS")

    # 8. CSCO RECOMMENDATION
    lines.append("\n[RECOMMENDATION] CSCO PROPOSAL")
    if state.recommendations:
        for rec in state.recommendations:
            lines.append(f"- Action: {rec.action}")
            lines.append(f"  Target: Supplier {rec.target_supplier_id}")
            if rec.reasons:
                lines.append(f"  Rationale: {rec.reasons[0]}")
            state_val = state.pending_approvals.get(rec.recommendation_id, ApprovalState.PENDING).value
            lines.append(f"  Approval State: {state_val}")
    else:
        lines.append("- NO RECOMMENDATION")

    # 9. ALTERNATIVE SOURCING (ONLY IF APPROVED)
    # Check if ANY recommendation was approved
    any_approved = any(val == ApprovalState.APPROVED for val in state.pending_approvals.values())
    if any_approved:
        lines.append("\n[DETERMINISTIC_CALCULATION] APPROVED ALTERNATIVE SOURCING")
        if state.alternative_suppliers:
            for alt in state.alternative_suppliers:
                lines.append(f"- {alt.candidate_name} ({alt.product_or_material})")
                lines.append(f"  ID: {alt.candidate_id} | In Graph: {alt.graph_presence}")
                lines.append(f"  Evidence State: {alt.evidence_status.value}")
                lines.append(f"  Ranking Score: {alt.ranking_score:.2f}")
                lines.append(f"  Connectivity: {alt.current_exposure_state}")
                lines.append(f"  Uncertainty: {alt.uncertainty}")
        else:
            lines.append("- NO CANDIDATES QUALIFIED")
    else:
        lines.append("\n[BLOCKED] ALTERNATIVE SOURCING REQUIRES APPROVAL")

    # 10. VISUALIZATION
    lines.append("\n[GRAPH_FACT] NETWORK VISUALIZATION PAYLOAD")
    if state.visualization_payload:
        lines.append(f"- Nodes generated: {len(state.visualization_payload.nodes)}")
        lines.append(f"- Edges generated: {len(state.visualization_payload.edges)}")
    else:
        lines.append("- NO VISUALIZATION AVAILABLE")

    lines.append("\n" + "="*80 + "\n")
    
    return "\n".join(lines)
