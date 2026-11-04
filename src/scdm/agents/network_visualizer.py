import logging
from typing import List, Dict, Set

from scdm.domain.schemas import (
    SupplierPath, 
    RiskResult, 
    AlternativeSupplier, 
    GraphVisualizationPayload, 
    VisualNode, 
    VisualEdge,
    ApprovalState
)

logger = logging.getLogger(__name__)

class NetworkVisualizerAgent:
    """
    Agent 4: Network Visualizer.
    Generates a deterministic, serializable subgraph payload based purely on 
    the authoritative output of the graph traversal and risk engine.
    """
    def __init__(self):
        pass

    def generate_visualization(
        self,
        focal_company_id: str,
        impacted_paths: List[SupplierPath],
        risk_results: List[RiskResult],
        alternative_suppliers: List[AlternativeSupplier],
        disrupted_supplier_ids: List[str]
    ) -> GraphVisualizationPayload:
        
        nodes: Dict[str, VisualNode] = {}
        edges: Set[tuple] = set()
        
        # 1. Map Risk Results for quick lookup
        risk_map = {r.supplier_id: r for r in risk_results}
        
        # 2. Add Focal Company
        if focal_company_id:
            nodes[focal_company_id] = VisualNode(
                id=focal_company_id,
                label=focal_company_id,
                is_focal=True,
                role="focal_company",
                tier=0
            )

        # 3. Process Impacted Paths
        for path in impacted_paths:
            path_nodes = path.ordered_path
            path_rels = path.relationships
            
            # Add nodes in path
            # The path is ordered from source (supplier) to target (focal company)
            # The distance from focal company can be inferred by position from the end
            for i, node_id in enumerate(path_nodes):
                if node_id not in nodes:
                    tier = len(path_nodes) - 1 - i
                    risk_level = risk_map[node_id].risk_level if node_id in risk_map else None
                    risk_score = risk_map[node_id].score if node_id in risk_map else None
                    
                    nodes[node_id] = VisualNode(
                        id=node_id,
                        label=node_id, # Can be enhanced if we had names in path
                        tier=tier,
                        role="supplier" if tier > 0 else "focal_company",
                        risk_level=risk_level,
                        risk_score=risk_score
                    )
                    
            # Add edges in path
            for i in range(len(path_nodes) - 1):
                source = path_nodes[i]
                target = path_nodes[i + 1]
                rel_type = path_rels[i] if i < len(path_rels) else "SUPPLIES"
                
                # Check if disrupted
                is_disrupted = (source in disrupted_supplier_ids) or (target in disrupted_supplier_ids)
                
                edges.add((source, target, rel_type, is_disrupted, False))

        # 4. Process Alternative Suppliers
        for alt in alternative_suppliers:
            # We only add them if they were actually generated (this implies APPROVED)
            if alt.candidate_id not in nodes:
                nodes[alt.candidate_id] = VisualNode(
                    id=alt.candidate_id,
                    label=alt.candidate_name,
                    is_candidate=True,
                    role="alternative_candidate"
                )
            # Link candidate to focal company if graph presence is True, or just conceptually
            edges.add((alt.candidate_id, focal_company_id, "ALTERNATIVE_SUPPLIES", False, True))
            
        # 5. Build Final Payload
        payload = GraphVisualizationPayload(
            focal_company_id=focal_company_id
        )
        
        for node in nodes.values():
            payload.nodes.append(node)
            
        for e in edges:
            payload.edges.append(VisualEdge(
                source=e[0],
                target=e[1],
                relationship_type=e[2],
                is_disrupted=e[3],
                is_alternative=e[4]
            ))
            
        logger.info(f"Generated visualization payload with {len(payload.nodes)} nodes and {len(payload.edges)} edges.")
        return payload
