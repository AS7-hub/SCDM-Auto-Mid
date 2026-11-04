import argparse
import logging
import sys
from typing import List, Type, TypeVar
from pydantic import BaseModel

from scdm.domain.state import WorkflowState
from scdm.domain.constants import ApprovalState, EvidenceStatus, DataLayer
from scdm.domain.schemas import EvidenceSource, EvidenceClaim, DisruptionEvent, RiskResult, Recommendation, AlternativeSupplier, SupplierPath, ExposureResult

# Mocks
from scdm.llm.client import LLMClient
from scdm.retrieval.search import DuckDuckGoSearchProvider
from scdm.analysis.resolution import EntityResolver
from scdm.analysis.traversal import GraphTraversal
from scdm.analysis.risk_engine import RiskEngine

from scdm.workflow.graph import WorkflowBuilder, GraphState
from scdm.reporting.executive_report import render_cli_report

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# --- MOCK CLASSES ---
class MockLLMClient(LLMClient):
    def __init__(self):
        super().__init__(budget=10)
    def generate_structured(self, prompt: str, schema: Type[T], max_retries: int = 1) -> T:
        if schema == DisruptionEvent:
            return DisruptionEvent(
                event_id="mock-1", disruption_type="SHORTAGE", 
                description="Mock disruption", affected_material="Palladium",
                layer=DataLayer.LLM_INTERPRETATION
            )
        if schema == Recommendation:
            return Recommendation(
                recommendation_id="mock-2", action="ALTERNATIVE SOURCING", 
                target_supplier_id="sup-123", risk_context="Mock risk",
                reasons=["Mock reason"], evidence_references=["url1"], 
                uncertainty="None", layer=DataLayer.RECOMMENDATION
            )
        if schema.__name__ == "ExtractedCandidates":
            # Have to mock internal structure
            class FakeCand:
                def __init__(self):
                    self.candidate_name="Mock Corp"
                    self.product_or_material="Palladium"
                    self.reasons="Test"
                    self.confidence_in_evidence="High"
            class FakeResp:
                def __init__(self):
                    self.candidates = [FakeCand()]
            return FakeResp()
        if schema.__name__ == "ExtractedProductClaims":
            class FakeClaim:
                def __init__(self):
                    self.supplier_name="Mock Supplier Co"
                    self.product_or_material="Palladium"
                    self.evidence_snippet="Mock snippet"
                    self.confidence="High"
            class FakeProductResp:
                def __init__(self):
                    self.claims = [FakeClaim()]
            return FakeProductResp()
        raise ValueError(f"Mock does not support {schema}")


class MockDDGProvider(DuckDuckGoSearchProvider):
    def search(self, query: str, max_results: int = 5) -> List[EvidenceSource]:
        return [
            EvidenceSource(source_url="http://mock.url", title="Mock Article", snippet="Mock snippet")
        ]

class MockRiskEngine(RiskEngine):
    def __init__(self):
        pass
    def calculate_risk(self, exposure: ExposureResult, focal_company_name: str = None) -> List[RiskResult]:
        if exposure.status != "RESOLVED" or not exposure.paths:
            return []
        # Mock deterministic risk for the first tier-1 supplier
        supplier_id = exposure.paths[0].ordered_path[-2] if len(exposure.paths[0].ordered_path) >= 2 else "sup-123"
        return [
            RiskResult(
                focal_company_id=exposure.focal_company_id, supplier_id=supplier_id, tier=1,
                score=0.9, risk_level="HIGH", formula_version="mock",
                reasons=["Mock topological reason"]
            )
        ]

class MockTraversal(GraphTraversal):
    def __init__(self):
        pass
    def get_upstream_exposure(self, focal_company_id: str, max_depth: int = 3) -> ExposureResult:
        from scdm.domain.schemas import ExposureStatus
        paths = [
            SupplierPath(focal_company_id=focal_company_id, ordered_path=["sup-123", focal_company_id], relationships=["SUPPLIES"], distance=1)
        ]
        return ExposureResult(
            focal_company_id=focal_company_id,
            status=ExposureStatus.RESOLVED,
            paths=paths,
            tier_groups={1: ["sup-123"]},
            max_depth_observed=1,
            path_count=1
        )
    def check_supplier_connectivity(self, supplier_id: str, focal_company_id: str) -> dict:
        return {
            "is_connected_to_focal": True,
            "min_distance_to_focal": 1,
            "total_downstream_customers": 5
        }

class MockResolver(EntityResolver):
    def __init__(self):
        pass
    def resolve_focal_company(self, query_text: str):
        from scdm.domain.schemas import ResolutionResult, ResolutionStatus
        if "ambiguous" in query_text.lower():
            return ResolutionResult(status=ResolutionStatus.AMBIGUOUS, candidates=[{"name": "Amb1"}, {"name": "Amb2"}])
        if "unknown" in query_text.lower():
            return ResolutionResult(status=ResolutionStatus.UNRESOLVED)
        return ResolutionResult(
            status=ResolutionStatus.RESOLVED,
            resolved_company_id="mock-alt-123",
            resolved_company_name=query_text
        )

# --- DEMO FACTORIES ---
def build_demo_components():
    from scdm.core.config import config
    
    if not config.gemini_api_key:
        raise ValueError("Cannot run DEMO or LIVE mode without gemini_api_key in environment.")
        
    resolver = EntityResolver(uri=config.neo4j_uri, user=config.neo4j_username, password=config.neo4j_password)
    traversal = GraphTraversal(uri=config.neo4j_uri, user=config.neo4j_username, password=config.neo4j_password)
    risk_engine = RiskEngine()
    llm = LLMClient(budget=3)
    ddg = DuckDuckGoSearchProvider(max_retries=1)
    return llm, ddg, resolver, traversal, risk_engine



def cli_approval_callback(wf: WorkflowState):
    print("\n*** DECISION REQUIRED ***")
    for rec in wf.recommendations:
        print(f"Recommendation: {rec.action} for Supplier {rec.target_supplier_id}")
    
    choice = input("Approve action? (y/N): ").strip().lower()
    approval = ApprovalState.APPROVED if choice == 'y' else ApprovalState.REJECTED
    
    for rec in wf.recommendations:
        wf.pending_approvals[rec.recommendation_id] = approval
        
    print(f"Status: {approval.value}\n")

def main():
    parser = argparse.ArgumentParser(description="SCDM Disruption Monitoring Workflow")
    parser.add_argument("--focal-company", type=str, required=True, help="ID of the focal company")
    parser.add_argument("--query", type=str, required=True, help="Disruption query")
    parser.add_argument("--mode", choices=["MOCK", "DEMO", "LIVE"], default="MOCK")
    args = parser.parse_args()

    print(f"Starting SCDM in {args.mode} mode...\n")

    if args.mode == "MOCK":
        llm = MockLLMClient()
        ddg = MockDDGProvider()
        resolver = MockResolver()
        traversal = MockTraversal()
        risk_engine = MockRiskEngine()

    else:
        llm, ddg, resolver, traversal, risk_engine = build_demo_components()
        
    builder = WorkflowBuilder(llm, ddg, resolver, traversal, risk_engine, approval_callback=cli_approval_callback)
    app = builder.build()
    
    initial_state = GraphState(workflow_state=WorkflowState(
        query=args.query,
        focal_company_id=args.focal_company
    ))

    current_state = initial_state
    
    for s in app.stream(initial_state):
        current_state = s

    # Final state
    final_wf = current_state[list(current_state.keys())[0]]["workflow_state"]
    print(render_cli_report(final_wf))

if __name__ == "__main__":
    main()
