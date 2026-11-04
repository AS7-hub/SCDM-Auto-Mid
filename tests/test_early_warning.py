import pytest
from scdm.analysis.early_warning import TemporalVulnerabilityMonitor
from scdm.domain.schemas import ExposureResult, SupplierPath, ExposureStatus

def test_early_warning_stable():
    monitor = TemporalVulnerabilityMonitor()
    
    # 5 paths, 5 Tier 1 suppliers (great diversity, low depth)
    exposure = ExposureResult(
        focal_company_id="focal-1",
        status=ExposureStatus.RESOLVED,
        tier_groups={1: ["sup-1", "sup-2", "sup-3", "sup-4", "sup-5"]},
        paths=[SupplierPath(focal_company_id="focal-1", ordered_path=[f"sup-{i}", "focal-1"], relationships=["SUPPLIES"], distance=1) for i in range(1, 6)],
        max_depth_observed=1,
        path_count=5
    )
    
    result = monitor.evaluate_vulnerability("focal-1", exposure, "Microchips")
    
    assert result.focal_company_id == "focal-1"
    assert result.overall_status == "STABLE"
    assert len(result.indicators) == 2
    
def test_early_warning_elevated_scarcity():
    monitor = TemporalVulnerabilityMonitor()
    
    # 1 Tier 1 supplier, high scarcity
    exposure = ExposureResult(
        focal_company_id="focal-1",
        status=ExposureStatus.RESOLVED,
        tier_groups={1: ["sup-1"]},
        paths=[SupplierPath(focal_company_id="focal-1", ordered_path=["sup-1", "focal-1"], relationships=["SUPPLIES"], distance=1)],
        max_depth_observed=1,
        path_count=1
    )
    
    result = monitor.evaluate_vulnerability("focal-1", exposure)
    
    assert result.overall_status == "ELEVATED"
    scarcity_ind = next(i for i in result.indicators if i.name == "Topological Scarcity")
    assert scarcity_ind.status == "ELEVATED"

def test_early_warning_high_depth():
    monitor = TemporalVulnerabilityMonitor()
    
    # Reaching depth 5
    exposure = ExposureResult(
        focal_company_id="focal-1",
        status=ExposureStatus.RESOLVED,
        tier_groups={1: ["sup-1", "sup-2"]},
        paths=[SupplierPath(focal_company_id="focal-1", ordered_path=["sup-1", "focal-1"], relationships=["SUPPLIES"], distance=1)],
        max_depth_observed=5,
        path_count=1
    )
    
    result = monitor.evaluate_vulnerability("focal-1", exposure)
    
    assert result.overall_status == "ELEVATED"
    depth_ind = next(i for i in result.indicators if i.name == "Depth Opacity")
    assert depth_ind.status == "ELEVATED"
