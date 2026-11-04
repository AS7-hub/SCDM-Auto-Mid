import pytest
from unittest.mock import MagicMock

from scdm.llm.client import LLMClient, LLMBudgetExceededError
from scdm.domain.schemas import DisruptionEvent, RiskResult, Recommendation, EvidenceSource
from scdm.domain.constants import DataLayer, EvidenceStatus
from scdm.agents.disruption_monitor import DisruptionMonitorAgent
from scdm.agents.csco import CSCOAgent
from scdm.agents.alternative_sourcing import AlternativeSourcingAgent, ExtractedCandidates, ExtractedCandidate

def test_disruption_agent_success():
    mock_client = MagicMock(spec=LLMClient)
    # Mock successful extraction
    mock_client.generate_structured.return_value = DisruptionEvent(
        event_id="test",
        disruption_type="MATERIAL_SHORTAGE",
        description="Shortage of palladium.",
        affected_material="Palladium",
        layer=DataLayer.LLM_INTERPRETATION
    )
    
    agent = DisruptionMonitorAgent(mock_client)
    res = agent.extract_event("query", [EvidenceSource(snippet="test")])
    
    assert res.affected_material == "Palladium"
    assert res.disruption_type == "MATERIAL_SHORTAGE"
    assert res.layer == DataLayer.LLM_INTERPRETATION

def test_disruption_agent_error_fallback():
    mock_client = MagicMock(spec=LLMClient)
    # Mock failure
    mock_client.generate_structured.side_effect = Exception("Quota exceeded")
    
    agent = DisruptionMonitorAgent(mock_client)
    res = agent.extract_event("query", [])
    
    # Should safely fallback
    assert res.disruption_type == "UNKNOWN"
    assert "LLM error" in res.description
    assert res.uncertainty == "HIGH - LLM ERROR"

def test_csco_agent_success():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate_structured.return_value = Recommendation(
        recommendation_id="test",
        action="ALTERNATIVE SOURCING",
        target_supplier_id="sup1",
        risk_context="HIGH risk",
        reasons=["High risk"],
        evidence_references=["source_1"],
        uncertainty="None",
        layer=DataLayer.RECOMMENDATION
    )
    
    agent = CSCOAgent(mock_client)
    risk = RiskResult(
        focal_company_id="focal",
        supplier_id="sup1",
        tier=1,
        score=0.9,
        risk_level="HIGH",
        formula_version="1"
    )
    disruption = DisruptionEvent(event_id="d1", disruption_type="X", description="Y")
    
    res = agent.generate_recommendation(risk, disruption, [])
    assert res.action == "ALTERNATIVE SOURCING"

def test_csco_agent_error_deterministic_fallback():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate_structured.side_effect = Exception("API Down")
    
    agent = CSCOAgent(mock_client)
    risk_high = RiskResult(
        focal_company_id="focal",
        supplier_id="sup1",
        tier=1,
        score=0.9,
        risk_level="HIGH",
        formula_version="1"
    )
    disruption = DisruptionEvent(event_id="d1", disruption_type="X", description="Y")
    
    res = agent.generate_recommendation(risk_high, disruption, [])
    
    # Fallback to deterministic mapping! HIGH -> ALTERNATIVE SOURCING
    assert res.action == "ALTERNATIVE SOURCING"
    assert "LLM error" in res.reasons[0]

from scdm.analysis.resolution import EntityResolver
from scdm.analysis.traversal import GraphTraversal
from scdm.domain.schemas import ResolutionStatus, ResolutionResult

def test_alternative_sourcing_agent_success():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate_structured.return_value = ExtractedCandidates(
        candidates=[
            ExtractedCandidate(candidate_name="AltCorp", product_or_material="Palladium", reasons="test", confidence_in_evidence="High")
        ]
    )
    
    mock_resolver = MagicMock(spec=EntityResolver)
    mock_resolver.resolve_focal_company.return_value = ResolutionResult(
        status=ResolutionStatus.RESOLVED,
        resolved_company_id="alt-123",
        resolved_company_name="AltCorp"
    )
    
    mock_traversal = MagicMock(spec=GraphTraversal)
    mock_traversal.check_supplier_connectivity.return_value = {
        "is_connected_to_focal": True,
        "min_distance_to_focal": 2,
        "total_downstream_customers": 10
    }
    
    agent = AlternativeSourcingAgent(mock_client, mock_resolver, mock_traversal)
    res = agent.extract_and_qualify_candidates("Palladium", "Desc", [EvidenceSource(snippet="test")], "focal-id")
    
    assert len(res) == 1
    assert res[0].candidate_name == "AltCorp"
    assert res[0].candidate_id == "alt-123"
    assert res[0].graph_presence is True
    assert res[0].evidence_status == EvidenceStatus.VALIDATED_CLAIM
    assert res[0].ranking_score > 0.5

def test_alternative_sourcing_agent_unresolved():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate_structured.return_value = ExtractedCandidates(
        candidates=[
            ExtractedCandidate(candidate_name="UnknownCorp", product_or_material="Palladium", reasons="test", confidence_in_evidence="High")
        ]
    )
    
    mock_resolver = MagicMock(spec=EntityResolver)
    mock_resolver.resolve_focal_company.return_value = ResolutionResult(status=ResolutionStatus.UNRESOLVED)
    mock_traversal = MagicMock(spec=GraphTraversal)
    
    agent = AlternativeSourcingAgent(mock_client, mock_resolver, mock_traversal)
    res = agent.extract_and_qualify_candidates("Palladium", "Desc", [EvidenceSource(snippet="test")], "focal-id")
    
    assert len(res) == 1
    assert res[0].candidate_name == "UnknownCorp"
    assert res[0].graph_presence is False
    assert res[0].evidence_status == EvidenceStatus.REVIEW_NEEDED
    assert res[0].ranking_score == 0.0

def test_alternative_sourcing_agent_ambiguous():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate_structured.return_value = ExtractedCandidates(
        candidates=[
            ExtractedCandidate(candidate_name="AmbiguousCorp", product_or_material="Palladium", reasons="test", confidence_in_evidence="High")
        ]
    )
    
    mock_resolver = MagicMock(spec=EntityResolver)
    mock_resolver.resolve_focal_company.return_value = ResolutionResult(
        status=ResolutionStatus.AMBIGUOUS,
        candidates=[{"name": "AmbiguousCorp1"}, {"name": "AmbiguousCorp2"}]
    )
    mock_traversal = MagicMock(spec=GraphTraversal)
    
    agent = AlternativeSourcingAgent(mock_client, mock_resolver, mock_traversal)
    res = agent.extract_and_qualify_candidates("Palladium", "Desc", [EvidenceSource(snippet="test")], "focal-id")
    
    assert len(res) == 1
    assert res[0].candidate_name == "AmbiguousCorp"
    assert res[0].graph_presence is False
    assert res[0].evidence_status == EvidenceStatus.REVIEW_NEEDED
    assert "AMBIGUOUS" in res[0].uncertainty
