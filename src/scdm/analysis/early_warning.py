from typing import List, Optional
from scdm.domain.schemas import ExposureResult, EarlyWarningResult, VulnerabilityIndicator

class TemporalVulnerabilityMonitor:
    """
    Since actual historical time-series data for supplier capabilities/relationships 
    is largely missing from this static canonical dataset, we do not fabricate a 
    predictive supervised model. 
    
    Instead, this implements deterministic topological proxies for temporal early 
    warning: measuring current topological scarcity and degree-concentration 
    against simulated structural baselines to flag vulnerability.
    """
    
    def __init__(self):
        # Baseline benchmarks could theoretically be loaded from configuration
        # For our graph, a node degree > 10 is considered highly concentrated.
        self.baseline_concentration_threshold = 10.0

    def evaluate_vulnerability(
        self, 
        focal_company_id: str,
        exposure: ExposureResult, 
        material_or_category: Optional[str] = None
    ) -> EarlyWarningResult:
        
        indicators = []
        overall_status = "STABLE"
        
        # 1. Topological Scarcity Indicator
        # Number of unique paths vs number of unique suppliers at Tier 1
        tier_1_suppliers = len(exposure.tier_groups.get(1, []))
        total_paths = len(exposure.paths)
        
        if tier_1_suppliers == 0:
            scarcity_status = "HIGH VULNERABILITY"
            reason = "Zero Tier-1 suppliers available in the impacted exposure graph."
        elif tier_1_suppliers == 1:
            scarcity_status = "ELEVATED"
            reason = "Single point of failure at Tier 1 (Monopoly exposure)."
        elif total_paths / tier_1_suppliers > 3:
            scarcity_status = "WATCH"
            reason = "High path concentration funneling into limited Tier-1 suppliers."
        else:
            scarcity_status = "STABLE"
            reason = "Adequate supplier diversity at Tier 1 relative to total network paths."
            
        indicators.append(
            VulnerabilityIndicator(
                name="Topological Scarcity",
                description="Measures lack of alternative supply paths.",
                current_value=float(tier_1_suppliers),
                trend="STABLE", # Without temporal data, we assume stable unless snapshot differs
                status=scarcity_status,
                reason=reason
            )
        )
        
        # 2. Path Depth Vulnerability (Reliance on deep, untraceable tiers)
        max_depth = exposure.max_depth_observed
        if max_depth >= 4:
            depth_status = "ELEVATED"
            reason = "Significant reliance on Tier 4+ suppliers increases opacity."
        elif max_depth == 3:
            depth_status = "WATCH"
            reason = "Exposure reaches Tier 3."
        else:
            depth_status = "STABLE"
            reason = "Exposure contained within transparent near-tiers (Tier 1-2)."
            
        indicators.append(
            VulnerabilityIndicator(
                name="Depth Opacity",
                description="Vulnerability stemming from deep supply chain reliance.",
                current_value=float(max_depth),
                trend="UNKNOWN",
                status=depth_status,
                reason=reason
            )
        )
        
        # Aggregate overall status
        status_weights = {"STABLE": 0, "WATCH": 1, "ELEVATED": 2, "HIGH VULNERABILITY": 3}
        max_severity = max([status_weights[ind.status] for ind in indicators] + [0])
        
        for name, weight in status_weights.items():
            if weight == max_severity:
                overall_status = name
                break
                
        return EarlyWarningResult(
            focal_company_id=focal_company_id,
            material_or_category=material_or_category,
            indicators=indicators,
            overall_status=overall_status
        )
