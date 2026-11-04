import json
import pytest
from pydantic import ValidationError
from scdm.domain.constants import DataLayer, RelationshipType, ApprovalState, EvidenceStatus
from scdm.domain.schemas import Company, SupplyChainRelationship, RiskResult, DisruptionEvent
from scdm.domain.state import WorkflowState

def test_company_serialization():
    # Test valid company creation
    comp = Company(company_id="12345", company_name="Test Corp", is_focal=True)
    assert comp.company_id == "12345"
    assert comp.layer == DataLayer.CANONICAL_DATA
    
    # Test serialization/deserialization
    serialized = comp.model_dump_json()
    deserialized = Company.model_validate_json(serialized)
    assert deserialized.company_id == "12345"

def test_company_missing_id():
    # ID is required
    with pytest.raises(ValidationError):
        Company(company_name="Missing ID Corp")

def test_relationship_semantics():
    rel = SupplyChainRelationship(
        relationship_type=RelationshipType.SUPPLIES,
        start_id="supplier_1",
        end_id="focal_1",
        source_company_id="focal_1",
        confidence=95.5
    )
    assert rel.relationship_type == RelationshipType.SUPPLIES
    assert rel.start_id == "supplier_1"
    
    # Invalid confidence (must be 0-100)
    with pytest.raises(ValidationError):
        SupplyChainRelationship(
            relationship_type=RelationshipType.SELLS_TO,
            start_id="focal_1",
            end_id="customer_1",
            source_company_id="focal_1",
            confidence=105.0 # Invalid
        )

def test_risk_result_deterministic_layer():
    rr = RiskResult(
        focal_company_id="focal",
        supplier_id="sup1",
        tier=1,
        score=0.75,
        risk_level="HIGH",
        formula_version="1.0-topological"
    )
    assert rr.provenance == DataLayer.DETERMINISTIC_RESULT
    assert rr.score == 0.75

def test_workflow_state():
    state = WorkflowState(query="Test query", focal_company_id="focal_1")
    assert state.current_step == "init"
    assert state.pending_approvals == {}
    
    state.pending_approvals["recommendation_1"] = ApprovalState.PENDING
    assert state.pending_approvals["recommendation_1"] == "PENDING"
