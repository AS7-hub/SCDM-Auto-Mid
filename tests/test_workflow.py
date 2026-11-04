import pytest
from unittest.mock import MagicMock
from scdm.workflow.graph import WorkflowBuilder, GraphState
from scdm.domain.state import WorkflowState
from scdm.domain.constants import ApprovalState
from scdm.domain.schemas import DisruptionEvent, ExposureResult, RiskResult, Recommendation, SupplierPath, EvidenceSource, ExposureStatus
from scdm.domain.constants import DataLayer
from scdm.llm.client import LLMBudgetExceededError

# Re-use mocks from __main__ or create specific ones here
class FakeLLMClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.budget = 10
        self.calls_successful = 0
    def generate_structured(self, prompt, schema, max_retries=1):
        if self.fail:
            raise Exception("Mock LLM Error")
        if self.calls_successful >= self.budget:
            raise LLMBudgetExceededError("Budget exceeded")
        self.calls_successful += 1
        
        if schema == DisruptionEvent:
            return DisruptionEvent(
                event_id="d1", disruption_type="SHORTAGE", description="Test",
                affected_material="Steel", layer=DataLayer.LLM_INTERPRETATION
            )
        if schema == Recommendation:
            return Recommendation(
                recommendation_id="r1", action="ALTERNATIVE SOURCING",
                target_supplier_id="sup1", risk_context="HIGH", reasons=["Test"],
                evidence_references=[], uncertainty="None", layer=DataLayer.RECOMMENDATION
            )
        if schema.__name__ == "ExtractedCandidates":
            class FakeCand:
                def __init__(self):
                    self.candidate_name="Mock Corp"
                    self.product_or_material="Steel"
                    self.reasons="Test"
                    self.confidence_in_evidence="High"
            class FakeResp:
                def __init__(self):
                    self.candidates = [FakeCand()]
            return FakeResp()
        if schema.__name__ == "ExtractedProductClaims":
            class FakeClaim:
                def __init__(self):
                    self.supplier_name="Mock Corp"
                    self.product_or_material="Steel"
                    self.evidence_snippet="Mock snippet"
                    self.confidence="High"
            class FakeProductResp:
                def __init__(self):
                    self.claims = [FakeClaim()]
            return FakeProductResp()
        raise ValueError(f"Unsupported schema {schema}")

class FakeDDG:
    def search(self, query, max_results=5):
        return [EvidenceSource(title="Test", snippet="Test", source_url="test")]

class FakeResolver:
    def resolve_focal_company(self, query):
        from scdm.domain.schemas import ResolutionResult, ResolutionStatus
        if query in ["Mock Corp", "focal"]:
            return ResolutionResult(
                status=ResolutionStatus.RESOLVED,
                resolved_company_id=query,
                resolved_company_name=query
            )
        return ResolutionResult(status=ResolutionStatus.UNRESOLVED)

class FakeTraversal:
    def get_upstream_exposure(self, focal_id, max_depth=3):
        return ExposureResult(
            focal_company_id=focal_id,
            status=ExposureStatus.RESOLVED,
            paths=[SupplierPath(focal_company_id=focal_id, ordered_path=["sup1", focal_id], relationships=["SUPPLIES"], distance=1)],
            tier_groups={1: ["sup1"]},
            max_depth_observed=1,
            path_count=1
        )
    def check_supplier_connectivity(self, supplier_id, focal_id):
        return {
            "is_connected_to_focal": True,
            "min_distance_to_focal": 1,
            "total_downstream_customers": 2
        }

class FakeRiskEngine:
    def calculate_risk(self, exposure, focal_name=None):
        if exposure.status != ExposureStatus.RESOLVED or not exposure.paths:
            return []
        return [RiskResult(
            focal_company_id=exposure.focal_company_id, supplier_id="sup1", tier=1,
            score=0.9, risk_level="HIGH", formula_version="1", reasons=["Test"]
        )]

@pytest.fixture
def workflow_components():
    return {
        "llm_client": FakeLLMClient(),
        "ddg_provider": FakeDDG(),
        "resolver": FakeResolver(),
        "traversal": FakeTraversal(),
        "risk_engine": FakeRiskEngine()
    }

def test_workflow_normal_completion(workflow_components):
    # A. normal MOCK workflow reaches completion
    def approve(wf):
        for rec in wf.recommendations:
            wf.pending_approvals[rec.recommendation_id] = ApprovalState.APPROVED
            
    builder = WorkflowBuilder(**workflow_components, approval_callback=approve)
    app = builder.build()
    
    state = GraphState(workflow_state=WorkflowState(query="test", focal_company_id="focal"))
    for s in app.stream(state):
        current = s
        
    wf = current[list(current.keys())[0]]["workflow_state"]
    assert len(wf.disruption_events) == 1
    assert len(wf.product_claims) == 1
    assert len(wf.risk_results) == 1
    assert len(wf.recommendations) == 1
    assert len(wf.alternative_suppliers) == 1

def test_workflow_rejected_approval(workflow_components):
    # E. human approval = REJECTED stops before alternative sourcing
    # H. alternative sourcing is never reachable without approval
    def reject(wf):
        for rec in wf.recommendations:
            wf.pending_approvals[rec.recommendation_id] = ApprovalState.REJECTED
            
    builder = WorkflowBuilder(**workflow_components, approval_callback=reject)
    app = builder.build()
    
    state = GraphState(workflow_state=WorkflowState(query="test", focal_company_id="focal"))
    for s in app.stream(state):
        current = s
        
    wf = current[list(current.keys())[0]]["workflow_state"]
    assert len(wf.alternative_suppliers) == 0 # Sourcing skipped

def test_workflow_pending_approval(workflow_components):
    # F. human approval = PENDING stops before alternative sourcing
    def pending(wf):
        pass # leaves them as PENDING (default)
            
    builder = WorkflowBuilder(**workflow_components, approval_callback=pending)
    app = builder.build()
    
    state = GraphState(workflow_state=WorkflowState(query="test", focal_company_id="focal"))
    for s in app.stream(state):
        current = s
        
    wf = current[list(current.keys())[0]]["workflow_state"]
    assert len(wf.alternative_suppliers) == 0 # Sourcing skipped

def test_llm_failure_does_not_corrupt_state(workflow_components):
    # I. an LLM failure/fallback does not corrupt workflow state
    workflow_components["llm_client"] = FakeLLMClient(fail=True)
    def approve(wf):
        for rec in wf.recommendations:
            wf.pending_approvals[rec.recommendation_id] = ApprovalState.APPROVED
            
    builder = WorkflowBuilder(**workflow_components, approval_callback=approve)
    app = builder.build()
    
    state = GraphState(workflow_state=WorkflowState(query="test", focal_company_id="focal"))
    for s in app.stream(state):
        current = s
        
    wf = current[list(current.keys())[0]]["workflow_state"]
    # Should fallback deterministically
    assert len(wf.disruption_events) == 1
    assert wf.disruption_events[0].disruption_type == "UNKNOWN"
    assert len(wf.recommendations) == 1
    assert wf.recommendations[0].action == "ALTERNATIVE SOURCING"
    # Alternative sourcing fails safely (returns empty list)
    assert len(wf.alternative_suppliers) == 0

def test_unresolved_focal_company(workflow_components):
    # B. entity-resolution unresolved/ambiguous condition is handled safely
    builder = WorkflowBuilder(**workflow_components)
    app = builder.build()
    
    # Empty focal company ID
    state = GraphState(workflow_state=WorkflowState(query="test", focal_company_id=None))
    for s in app.stream(state):
        current = s
        
    wf = current[list(current.keys())[0]]["workflow_state"]
    assert "No focal company provided or resolved." in wf.errors
    # Graph traversal should skip or fail gracefully
    assert len(wf.impacted_paths) == 0

def test_deterministic_risk_preserved(workflow_components):
    # C. deterministic risk node receives and preserves RiskResult
    # D. CSCO recommendation consumes deterministic risk without modifying it
    builder = WorkflowBuilder(**workflow_components)
    app = builder.build()
    
    state = GraphState(workflow_state=WorkflowState(query="test", focal_company_id="focal"))
    for s in app.stream(state):
        current = s
        
    wf = current[list(current.keys())[0]]["workflow_state"]
    assert len(wf.risk_results) == 1
    assert wf.risk_results[0].score == 0.9
    assert wf.risk_results[0].risk_level == "HIGH"

def test_llm_budget_enforcement(workflow_components):
    # J. LLM call budget enforcement remains respected
    llm = FakeLLMClient()
    llm.budget = 0 # Budget exhausted immediately
    workflow_components["llm_client"] = llm
    
    builder = WorkflowBuilder(**workflow_components)
    app = builder.build()
    
    state = GraphState(workflow_state=WorkflowState(query="test", focal_company_id="focal"))
    for s in app.stream(state):
        current = s
        
    wf = current[list(current.keys())[0]]["workflow_state"]
    assert wf.disruption_events[0].disruption_type == "UNKNOWN"
