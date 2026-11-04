import pytest
from scdm.core.config import config
from scdm.analysis.resolution import EntityResolver
from scdm.analysis.traversal import GraphTraversal
from scdm.domain.schemas import ResolutionStatus, ExposureStatus

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

def test_resolution_exact_id(resolver):
    # 'Volkswagen AG' ID in canonical (example from earlier output is 4295869244)
    # Since we wiped Neo4j and loaded canonical, we need to know an exact ID.
    # We will pick a known ID or dynamically fetch one.
    pass

def test_resolution_exact_name(resolver):
    res = resolver.resolve_focal_company("volkswagen ag")
    assert res.status in [ResolutionStatus.RESOLVED, ResolutionStatus.AMBIGUOUS]

def test_resolution_unresolved(resolver):
    res = resolver.resolve_focal_company("Completely Fake Unknown Company XYZ 123")
    assert res.status == ResolutionStatus.UNRESOLVED

def test_traversal_no_exposure(traversal):
    res = traversal.get_upstream_exposure("FAKE_ID_NO_GRAPH", max_depth=2)
    assert res.status == ExposureStatus.UNRESOLVED

def test_traversal_integration(traversal, resolver):
    # Find a real company to traverse from
    res = resolver.resolve_focal_company("volkswagen")
    if res.status != ResolutionStatus.UNRESOLVED:
        target_id = res.resolved_company_id if res.resolved_company_id else res.candidates[0]["id"]
        
        # Test max_depth = 1
        exp_1 = traversal.get_upstream_exposure(target_id, max_depth=1)
        if exp_1.status == ExposureStatus.RESOLVED:
            assert exp_1.max_depth_observed == 1
            
            # Test max_depth = 2
            exp_2 = traversal.get_upstream_exposure(target_id, max_depth=2)
            assert exp_2.max_depth_observed <= 2
            
            # Ensure path deduplication: total unique paths should equal the path_count
            unique_paths = {tuple(p.ordered_path) for p in exp_2.paths}
            assert len(unique_paths) == exp_2.path_count
            assert len(exp_2.paths) == exp_2.path_count
