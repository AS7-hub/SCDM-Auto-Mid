from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from scdm.domain.schemas import (
    DisruptionEvent,
    EvidenceSource,
    RiskResult,
    Recommendation,
    AlternativeSupplier,
    SupplierPath,
    EvidenceClaim,
    GraphVisualizationPayload
)
from scdm.domain.constants import ApprovalState

class WorkflowState(BaseModel):
    """
    Shared state contract for LangGraph orchestration.
    """
    # Request inputs
    query: str = ""
    focal_company_id: Optional[str] = None
    
    # Internal context
    disruption_events: List[DisruptionEvent] = Field(default_factory=list)
    gathered_evidence: List[EvidenceSource] = Field(default_factory=list)
    impacted_paths: List[SupplierPath] = Field(default_factory=list)
    product_claims: List[EvidenceClaim] = Field(default_factory=list)
    
    # Analysis outputs
    risk_results: List[RiskResult] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    alternative_suppliers: List[AlternativeSupplier] = Field(default_factory=list)
    
    # Visualization
    visualization_payload: Optional[GraphVisualizationPayload] = None
    
    # Human in the loop
    pending_approvals: Dict[str, ApprovalState] = Field(default_factory=dict)
    
    # Agent/Workflow metadata
    current_step: str = "init"
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
