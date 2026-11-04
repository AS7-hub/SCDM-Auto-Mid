import logging
from typing import List, Dict, Any, Tuple
from collections import defaultdict

from scdm.domain.schemas import ExposureResult, RiskResult

logger = logging.getLogger(__name__)

class RiskEngine:
    """
    Deterministic Supplier Risk Engine.
    Operates strictly on the graph topology provided by ExposureResult.
    """
    def __init__(self):
        self.formula_version = "1.0-topological"
        self.weights = {
            "exposure_breadth": 0.35,
            "path_concentration": 0.25,
            "downstream_criticality": 0.20,
            "tier1_centrality": 0.10,
            "exposure_depth": 0.10
        }
        self.thresholds = {
            "HIGH": 0.60,
            "MEDIUM": 0.45
        }

    def _determine_risk_level(self, score: float) -> str:
        if score >= self.thresholds["HIGH"]:
            return "HIGH"
        elif score >= self.thresholds["MEDIUM"]:
            return "MEDIUM"
        return "LOW"

    def calculate_risk(self, exposure: ExposureResult, focal_company_name: str = None) -> List[RiskResult]:
        """
        Calculates deterministic risk scores for all Tier-1 suppliers in the given exposure graph.
        """
        if exposure.status != "RESOLVED" or not exposure.paths:
            return []

        # Find all Tier-1 suppliers
        # By definition, a Tier-1 supplier is at distance 1 from focal.
        # In ordered_path (Supplier -> ... -> Focal), focal is at index -1, Tier-1 is at index -2.
        
        # 1. Map paths to Tier-1 suppliers
        t1_paths = defaultdict(list)
        for p in exposure.paths:
            if len(p.ordered_path) >= 2:
                t1_id = p.ordered_path[-2]
                t1_paths[t1_id].append(p)
                
        t1_suppliers = list(t1_paths.keys())
        total_t1 = len(t1_suppliers)
        total_paths = len(exposure.paths)
        
        if total_t1 == 0:
            return []

        # 2. Extract Raw Features
        raw_features = {}
        for t1 in t1_suppliers:
            paths = t1_paths[t1]
            
            # Exposure Depth: max length of upstream path
            depth = max([len(p.ordered_path) - 1 for p in paths])
            
            # Path Concentration: paths through T1 / total paths
            concentration = len(paths) / total_paths
            
            # Downstream Criticality: topological scarcity
            criticality = 1.0 / total_t1
            
            # Tier-1 Centrality: number of immediate unique Tier-2 suppliers feeding this T1
            t2_nodes = set()
            for p in paths:
                if len(p.ordered_path) >= 3:
                    t2_nodes.add(p.ordered_path[-3])
            centrality = len(t2_nodes)
            
            # Exposure Breadth: distance-decayed sum of unique upstream nodes
            unique_nodes = {} # node_id -> min_distance_to_t1
            for p in paths:
                # p.ordered_path is [..., T2, T1, Focal]
                # Distance to T1 is (len(ordered_path) - 2) - index
                for i, node_id in enumerate(p.ordered_path[:-2]):
                    dist_to_t1 = (len(p.ordered_path) - 2) - i
                    if node_id not in unique_nodes or dist_to_t1 < unique_nodes[node_id]:
                        unique_nodes[node_id] = dist_to_t1
                        
            breadth = 0.0
            for node_id, dist in unique_nodes.items():
                breadth += 1.0 / (2 ** (dist - 1))
                
            raw_features[t1] = {
                "exposure_depth": float(depth),
                "path_concentration": float(concentration),
                "downstream_criticality": float(criticality),
                "tier1_centrality": float(centrality),
                "exposure_breadth": float(breadth)
            }
            
        # 3. Normalize Features globally across all T1s
        max_depth = max([f["exposure_depth"] for f in raw_features.values()]) if raw_features else 1.0
        max_centrality = max([f["tier1_centrality"] for f in raw_features.values()]) if raw_features else 1.0
        max_breadth = max([f["exposure_breadth"] for f in raw_features.values()]) if raw_features else 1.0
        
        # Prevent zero division
        if max_depth == 0: max_depth = 1.0
        if max_centrality == 0: max_centrality = 1.0
        if max_breadth == 0: max_breadth = 1.0

        results = []
        for t1 in t1_suppliers:
            raw = raw_features[t1]
            
            norm = {
                "exposure_depth": raw["exposure_depth"] / max_depth,
                "path_concentration": raw["path_concentration"], # Already [0,1]
                "downstream_criticality": raw["downstream_criticality"], # Already [0,1]
                "tier1_centrality": raw["tier1_centrality"] / max_centrality,
                "exposure_breadth": raw["exposure_breadth"] / max_breadth
            }
            
            # 4. Calculate Weighted Score
            contributions = {}
            score = 0.0
            for k, w in self.weights.items():
                c = norm[k] * w
                contributions[k] = c
                score += c
                
            # 5. Explainability Reasons
            reasons = []
            if norm["exposure_breadth"] > 0.8:
                reasons.append(f"High upstream exposure breadth (Raw: {raw['exposure_breadth']:.2f}).")
            if norm["path_concentration"] > 0.5:
                reasons.append(f"Critical choke point: processes {raw['path_concentration']*100:.1f}% of all exposed paths.")
            if raw["downstream_criticality"] > 0.5:
                reasons.append("High topological downstream criticality (few alternative Tier-1s).")
                
            res = RiskResult(
                focal_company_id=exposure.focal_company_id,
                focal_company_name=focal_company_name,
                supplier_id=t1,
                supplier_name=None, # Cannot infer from ID alone without graph lookup, usually provided separately or by agent
                tier=1,
                score=round(score, 4),
                risk_level=self._determine_risk_level(score),
                raw_features=raw,
                normalized_features=norm,
                feature_weights=self.weights,
                feature_contributions=contributions,
                formula_version=self.formula_version,
                reasons=reasons
            )
            results.append(res)
            
        # 6. Rank deterministic sorting
        # Descending by score, ascending by ID for stable tie-breaking
        results.sort(key=lambda x: (-x.score, x.supplier_id))
        
        return results
