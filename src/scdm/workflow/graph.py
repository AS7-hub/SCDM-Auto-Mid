import logging
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from scdm.domain.state import WorkflowState
from scdm.domain.constants import ApprovalState
from scdm.llm.client import LLMClient
from scdm.retrieval.search import DuckDuckGoSearchProvider
from scdm.agents.disruption_monitor import DisruptionMonitorAgent
from scdm.agents.csco import CSCOAgent
from scdm.agents.alternative_sourcing import AlternativeSourcingAgent
from scdm.agents.product_search import ProductSearchAgent
from scdm.agents.network_visualizer import NetworkVisualizerAgent
from scdm.analysis.resolution import EntityResolver
from scdm.analysis.traversal import GraphTraversal
from scdm.analysis.risk_engine import RiskEngine
from scdm.domain.schemas import ExposureResult

logger = logging.getLogger(__name__)

class GraphState(TypedDict):
    workflow_state: WorkflowState

class WorkflowBuilder:
    def __init__(self, 
                 llm_client: LLMClient,
                 ddg_provider: DuckDuckGoSearchProvider,
                 resolver: EntityResolver,
                 traversal: GraphTraversal,
                 risk_engine: RiskEngine,
                 approval_callback=None):
        
        self.llm_client = llm_client
        self.ddg_provider = ddg_provider
        self.resolver = resolver
        self.traversal = traversal
        self.risk_engine = risk_engine
        self.approval_callback = approval_callback
        
        self.monitor_agent = DisruptionMonitorAgent(llm_client)
        self.csco_agent = CSCOAgent(llm_client)
        self.sourcing_agent = AlternativeSourcingAgent(llm_client, resolver, traversal)
        self.product_agent = ProductSearchAgent(llm_client, ddg_provider, resolver)
        self.visualizer_agent = NetworkVisualizerAgent()

    def node_retrieve_evidence(self, state: GraphState) -> GraphState:
        wf = state["workflow_state"]
        logger.info("[1/7] Retrieving external evidence")
        wf.current_step = "retrieve_evidence"
        # Only search if we don't already have evidence mock injected
        if not wf.gathered_evidence:
            results = self.ddg_provider.search(wf.query, max_results=3)
            wf.gathered_evidence.extend(results)
        return {"workflow_state": wf}

    def node_disruption_understanding(self, state: GraphState) -> GraphState:
        wf = state["workflow_state"]
        logger.info("[2/7] Detecting disruption context")
        wf.current_step = "disruption_understanding"
        event = self.monitor_agent.extract_event(wf.query, wf.gathered_evidence)
        wf.disruption_events.append(event)
        return {"workflow_state": wf}

    def node_product_search(self, state: GraphState) -> GraphState:
        wf = state["workflow_state"]
        logger.info("[3/7] Searching product context")
        wf.current_step = "product_search"
        
        disruption = wf.disruption_events[0] if wf.disruption_events else None
        if disruption and disruption.affected_material:
            # We search for the material. If focal_company_id exists, we could use its name. 
            # But at this stage, focal_company is not resolved. We just search the material.
            claims = self.product_agent.search_product_context(disruption.affected_material)
            wf.product_claims.extend(claims)
            
        return {"workflow_state": wf}

    def node_entity_resolution(self, state: GraphState) -> GraphState:
        wf = state["workflow_state"]
        logger.info("[4/7] Resolving supply-chain entities")
        wf.current_step = "entity_resolution"
        
        if not wf.focal_company_id:
            # Try resolving from query if no focal company ID was provided
            res = self.resolver.resolve_focal_company(wf.query)
            if res.status.name == "RESOLVED":
                wf.focal_company_id = res.resolved_company_id
            else:
                wf.errors.append(f"No focal company provided or resolved. Status: {res.status.name}. Reason: {res.reason}")
                return {"workflow_state": wf}
        else:
            # We must resolve the provided focal company ID to ensure it exists in graph
            # The id provided could just be a name snippet for demo/mock
            res = self.resolver.resolve_focal_company(wf.focal_company_id)
            if res.status.name == "RESOLVED":
                wf.focal_company_id = res.resolved_company_id
            else:
                wf.errors.append(f"Focal company '{wf.focal_company_id}' resolution failed: {res.status.name}. Reason: {res.reason}")
                wf.focal_company_id = None  # Clear to prevent invalid traversal
                
        return {"workflow_state": wf}

    def node_graph_traversal(self, state: GraphState) -> GraphState:
        wf = state["workflow_state"]
        logger.info("[5/7] Traversing supply-chain graph")
        wf.current_step = "graph_traversal"
        if not wf.focal_company_id:
            logger.warning("Skipping graph traversal because focal_company_id is missing.")
            return {"workflow_state": wf}
        if not wf.impacted_paths: # if not mocked
            exposure = self.traversal.get_upstream_exposure(wf.focal_company_id, max_depth=3)
            wf.impacted_paths = exposure.paths
        return {"workflow_state": wf}

    def node_risk_calculation(self, state: GraphState) -> GraphState:
        wf = state["workflow_state"]
        logger.info("[6/7] Calculating supplier risk")
        wf.current_step = "risk_calculation"
        
        # Calculate risk for all suppliers in the paths
        from scdm.domain.schemas import ExposureResult
        if not wf.risk_results and wf.impacted_paths:
            exposure = ExposureResult(
                status="RESOLVED",
                focal_company_id=wf.focal_company_id,
                paths=wf.impacted_paths
            )
            rrs = self.risk_engine.calculate_risk(exposure)
            if rrs:
                wf.risk_results.extend(rrs)
        return {"workflow_state": wf}

    def node_csco_decision(self, state: GraphState) -> GraphState:
        wf = state["workflow_state"]
        logger.info("[7/7] Preparing executive assessment")
        wf.current_step = "csco_decision"
        
        disruption = wf.disruption_events[0] if wf.disruption_events else None
        if not disruption:
            return {"workflow_state": wf}
            
        # For demo, just get recommendation for the highest risk supplier
        if wf.risk_results:
            highest_risk = sorted(wf.risk_results, key=lambda x: x.score, reverse=True)[0]
            rec = self.csco_agent.generate_recommendation(highest_risk, disruption, wf.gathered_evidence)
            wf.recommendations.append(rec)
            # Default state to PENDING approval
            wf.pending_approvals[rec.recommendation_id] = ApprovalState.PENDING
            
        return {"workflow_state": wf}

    def node_human_approval(self, state: GraphState) -> GraphState:
        wf = state["workflow_state"]
        logger.info("[Approval Gate] Waiting for human decision")
        wf.current_step = "human_approval"
        
        if self.approval_callback:
            self.approval_callback(wf)
            
        return {"workflow_state": wf}
        
    def node_alternative_sourcing(self, state: GraphState) -> GraphState:
        wf = state["workflow_state"]
        logger.info("[8] Alternative Sourcing")
        wf.current_step = "alternative_sourcing"
        
        disruption = wf.disruption_events[0] if wf.disruption_events else None
        if not disruption or not disruption.affected_material:
            return {"workflow_state": wf}
            
        candidates = self.sourcing_agent.extract_and_qualify_candidates(
            material=disruption.affected_material,
            disruption_desc=disruption.description,
            evidence=wf.gathered_evidence,
            focal_company_id=wf.focal_company_id
        )
        
        wf.alternative_suppliers.extend(candidates)
        return {"workflow_state": wf}

    def node_network_visualization(self, state: GraphState) -> GraphState:
        wf = state["workflow_state"]
        logger.info("[Visualization] Generating network visualization payload")
        wf.current_step = "network_visualization"
        
        disrupted_ids = []
        if wf.disruption_events and wf.disruption_events[0].affected_entities:
            disrupted_ids = wf.disruption_events[0].affected_entities
            
        payload = self.visualizer_agent.generate_visualization(
            focal_company_id=wf.focal_company_id,
            impacted_paths=wf.impacted_paths,
            risk_results=wf.risk_results,
            alternative_suppliers=wf.alternative_suppliers,
            disrupted_supplier_ids=disrupted_ids
        )
        wf.visualization_payload = payload
        return {"workflow_state": wf}

    def should_continue_sourcing(self, state: GraphState) -> str:
        wf = state["workflow_state"]
        # Check if ANY recommendation is APPROVED
        for state_val in wf.pending_approvals.values():
            if state_val == ApprovalState.APPROVED:
                return "source"
        return "stop"

    def should_continue_after_disruption(self, state: GraphState) -> str:
        wf = state["workflow_state"]
        if wf.errors:
            return "stop"
        return "continue"
        
    def should_continue_after_resolution(self, state: GraphState) -> str:
        wf = state["workflow_state"]
        if wf.errors or not wf.focal_company_id:
            return "stop"
        return "continue"

    def build(self) -> StateGraph:
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("retrieve_evidence", self.node_retrieve_evidence)
        workflow.add_node("disruption_understanding", self.node_disruption_understanding)
        workflow.add_node("product_search", self.node_product_search)
        workflow.add_node("entity_resolution", self.node_entity_resolution)
        workflow.add_node("graph_traversal", self.node_graph_traversal)
        workflow.add_node("risk_calculation", self.node_risk_calculation)
        workflow.add_node("csco_decision", self.node_csco_decision)
        workflow.add_node("human_approval", self.node_human_approval)
        workflow.add_node("alternative_sourcing", self.node_alternative_sourcing)
        workflow.add_node("network_visualization", self.node_network_visualization)
        
        # Add edges
        workflow.add_edge(START, "retrieve_evidence")
        workflow.add_edge("retrieve_evidence", "disruption_understanding")
        
        workflow.add_conditional_edges(
            "disruption_understanding",
            self.should_continue_after_disruption,
            {
                "continue": "product_search",
                "stop": END
            }
        )
        
        workflow.add_edge("product_search", "entity_resolution")
        
        workflow.add_conditional_edges(
            "entity_resolution",
            self.should_continue_after_resolution,
            {
                "continue": "graph_traversal",
                "stop": END
            }
        )
        
        workflow.add_edge("graph_traversal", "risk_calculation")
        workflow.add_edge("risk_calculation", "csco_decision")
        workflow.add_edge("csco_decision", "human_approval")
        
        workflow.add_conditional_edges(
            "human_approval",
            self.should_continue_sourcing,
            {
                "source": "alternative_sourcing",
                "stop": "network_visualization"
            }
        )
        
        workflow.add_edge("alternative_sourcing", "network_visualization")
        workflow.add_edge("network_visualization", END)
        return workflow.compile()
