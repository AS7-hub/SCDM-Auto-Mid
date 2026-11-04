import pytest
from scdm.agents.network_visualizer import NetworkVisualizerAgent
from scdm.domain.schemas import SupplierPath, RiskResult, AlternativeSupplier

def test_network_visualizer_deterministic_payload():
    visualizer = NetworkVisualizerAgent()
    
    impacted_paths = [
        SupplierPath(focal_company_id="focal-1", ordered_path=["sup-1", "sup-2", "focal-1"], relationships=["SUPPLIES", "SUPPLIES"], distance=2),
        SupplierPath(focal_company_id="focal-1", ordered_path=["sup-3", "focal-1"], relationships=["SELLS_TO"], distance=1)
    ]
    
    risk_results = [
        RiskResult(focal_company_id="focal-1", supplier_id="sup-1", tier=2, score=0.9, risk_level="HIGH", formula_version="1", reasons=[]),
        RiskResult(focal_company_id="focal-1", supplier_id="sup-3", tier=1, score=0.3, risk_level="LOW", formula_version="1", reasons=[])
    ]
    
    alternative_suppliers = [
        AlternativeSupplier(candidate_id="alt-1", candidate_name="Alt Corp", product_or_material="Test", uncertainty="None", graph_presence=False)
    ]
    
    disrupted_ids = ["sup-1"]
    
    payload = visualizer.generate_visualization(
        focal_company_id="focal-1",
        impacted_paths=impacted_paths,
        risk_results=risk_results,
        alternative_suppliers=alternative_suppliers,
        disrupted_supplier_ids=disrupted_ids
    )
    
    # Assert focal company
    assert payload.focal_company_id == "focal-1"
    
    # Assert nodes
    node_ids = {n.id for n in payload.nodes}
    assert "focal-1" in node_ids
    assert "sup-1" in node_ids
    assert "sup-2" in node_ids
    assert "sup-3" in node_ids
    assert "alt-1" in node_ids
    
    # Assert risk context applied correctly
    n_sup1 = next(n for n in payload.nodes if n.id == "sup-1")
    assert n_sup1.risk_level == "HIGH"
    assert n_sup1.tier == 2
    
    n_sup2 = next(n for n in payload.nodes if n.id == "sup-2")
    assert n_sup2.risk_level is None
    assert n_sup2.tier == 1
    
    # Assert edges
    edges = {(e.source, e.target, e.is_disrupted, e.is_alternative) for e in payload.edges}
    
    assert ("sup-1", "sup-2", True, False) in edges
    assert ("sup-2", "focal-1", False, False) in edges
    assert ("sup-3", "focal-1", False, False) in edges
    assert ("alt-1", "focal-1", False, True) in edges
