import pytest
from scdm.analysis.risk_engine import RiskEngine
from scdm.domain.schemas import ExposureResult, SupplierPath, ExposureStatus
from scdm.domain.constants import RelationshipType

from scdm.core.config import config
from scdm.analysis.resolution import EntityResolver
from scdm.analysis.traversal import GraphTraversal

def test_risk_engine_synthetic_basic():
    engine = RiskEngine()
    
    # Synthetic paths
    # Focal: F
    # T1 Supplier A (ID: "A") -> F
    # T2 Supplier B (ID: "B") -> A
    # T1 Supplier C (ID: "C") -> F
    
    p1 = SupplierPath(
        focal_company_id="F",
        ordered_path=["B", "A", "F"],
        relationships=[RelationshipType.SUPPLIES, RelationshipType.SUPPLIES],
        distance=2
    )
    p2 = SupplierPath(
        focal_company_id="F",
        ordered_path=["C", "F"],
        relationships=[RelationshipType.SUPPLIES],
        distance=1
    )
    
    exposure = ExposureResult(
        focal_company_id="F",
        status=ExposureStatus.RESOLVED,
        paths=[p1, p2],
        tier_groups={1: ["A", "C"], 2: ["B"]},
        max_depth_observed=2,
        path_count=2
    )
    
    results = engine.calculate_risk(exposure)
    
    assert len(results) == 2, "Should calculate risk for exactly 2 Tier-1 suppliers"
    
    # Order should be deterministic
    assert results[0].supplier_id in ["A", "C"]
    
    # Check features for "A"
    res_a = next(r for r in results if r.supplier_id == "A")
    assert res_a.raw_features["exposure_depth"] == 2
    assert res_a.raw_features["path_concentration"] == 0.5 # 1 out of 2 paths
    assert res_a.raw_features["downstream_criticality"] == 0.5 # 2 T1s total
    assert res_a.raw_features["tier1_centrality"] == 1 # 1 T2 feeding it
    assert res_a.raw_features["exposure_breadth"] == 1.0 # 1 T2 at dist 1 -> 1/(2^0) = 1.0
    
    # Check features for "C"
    res_c = next(r for r in results if r.supplier_id == "C")
    assert res_c.raw_features["exposure_depth"] == 1
    assert res_c.raw_features["path_concentration"] == 0.5
    assert res_c.raw_features["downstream_criticality"] == 0.5
    assert res_c.raw_features["tier1_centrality"] == 0
    assert res_c.raw_features["exposure_breadth"] == 0.0

    # Test normalization bounds
    for r in results:
        for val in r.normalized_features.values():
            assert 0.0 <= val <= 1.0

def test_risk_engine_empty_exposure():
    engine = RiskEngine()
    exposure = ExposureResult(
        focal_company_id="F",
        status=ExposureStatus.NO_GRAPH_EXPOSURE,
        paths=[]
    )
    results = engine.calculate_risk(exposure)
    assert len(results) == 0

@pytest.fixture(scope="module")
def resolver():
    res = EntityResolver(config.neo4j_uri, config.neo4j_username, "password")
    yield res
    res.close()

@pytest.fixture(scope="module")
def traversal():
    trav = GraphTraversal(config.neo4j_uri, config.neo4j_username, "password")
    yield trav
    trav.close()

def test_risk_engine_live_integration(resolver, traversal):
    # This targets the real graph
    res = resolver.resolve_focal_company("volkswagen")
    if res.status != "UNRESOLVED":
        target_id = res.resolved_company_id if res.resolved_company_id else res.candidates[0]["id"]
        
        exp = traversal.get_upstream_exposure(target_id, max_depth=3)
        if exp.status == ExposureStatus.RESOLVED:
            engine = RiskEngine()
            risk_results = engine.calculate_risk(exp)
            
            # Since VW has many Tier-1s, check that we get results
            assert len(risk_results) > 0
            
            # Ensure descending deterministic sort
            scores = [r.score for r in risk_results]
            assert scores == sorted(scores, reverse=True)
            
            # Inspect the top supplier
            top_supplier = risk_results[0]
            assert top_supplier.score >= 0.0
            assert top_supplier.score <= 1.0
            assert top_supplier.tier == 1
            assert "1.0-topological" in top_supplier.formula_version
            assert top_supplier.provenance == "DETERMINISTIC_RESULT"
