from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from scdm.domain.constants import DataLayer, RelationshipType, ApprovalState, EvidenceStatus

# A. Company
class Company(BaseModel):
    company_id: str = Field(description="Unique string identifier for the company")
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    country_region: Optional[str] = None
    industry: Optional[str] = None
    is_focal: bool = Field(default=False, description="Whether this company is a designated focal company")
    layer: DataLayer = Field(default=DataLayer.CANONICAL_DATA)

# B. Supply-chain relationship
class SupplyChainRelationship(BaseModel):
    relationship_type: RelationshipType
    start_id: str
    end_id: str
    source_company_id: str = Field(description="ID of the focal company from whose dataset this edge was derived")
    source_company_name: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=100.0)
    freshness: Optional[str] = None
    last_update_date: Optional[str] = None
    snippet_count: Optional[int] = None
    source_file: Optional[str] = None
    layer: DataLayer = Field(default=DataLayer.CANONICAL_DATA)

# C. Focal company
class FocalCompany(Company):
    is_focal: bool = True
    # Note: Tier is not a permanent attribute of FocalCompany. It's dynamically calculated in a path.

# D. Disruption event
class DisruptionEvent(BaseModel):
    event_id: str
    disruption_type: str
    description: str
    location: Optional[str] = None
    affected_material: Optional[str] = None
    affected_entities: List[str] = Field(default_factory=list, description="List of company names or IDs potentially affected")
    event_date: Optional[datetime] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    extraction_metadata: Dict[str, Any] = Field(default_factory=dict)
    uncertainty: Optional[str] = None
    layer: DataLayer = Field(default=DataLayer.LLM_INTERPRETATION)

# E. Evidence & Retrieval
class EvidenceSource(BaseModel):
    """A deterministic search result or provided document before validation."""
    source_url: Optional[str] = None
    title: Optional[str] = None
    snippet: Optional[str] = None
    publication_date: Optional[str] = None
    retrieved_timestamp: Optional[datetime] = None
    search_query: Optional[str] = None
    provider: Optional[str] = None
    status: EvidenceStatus = Field(default=EvidenceStatus.SEARCH_RESULT_FOUND)
    source_metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance: DataLayer = Field(default=DataLayer.EXTERNAL_EVIDENCE)

class EvidenceClaim(BaseModel):
    """A claim derived from sources or models."""
    claim_id: str
    claim_text: str
    subject_id: Optional[str] = None
    subject_name: Optional[str] = None
    predicate: Optional[str] = None
    object_value: Optional[str] = None
    uncertainty: Optional[str] = None
    sources: List[EvidenceSource] = Field(default_factory=list)
    status: EvidenceStatus = Field(default=EvidenceStatus.UNVERIFIED)
    provenance: DataLayer = Field(default=DataLayer.EXTERNAL_EVIDENCE)

# F. Graph path / exposure
class SupplierPath(BaseModel):
    focal_company_id: str
    ordered_path: List[str] = Field(description="Ordered list of company IDs from start (supplier) to focal company")
    relationships: List[RelationshipType] = Field(description="Ordered list of relationship types connecting the path")
    distance: int = Field(description="Dynamically derived tier/distance relative to the focal company")
    affected_status: bool = Field(default=False, description="Whether this specific path is flagged as affected")
    provenance: DataLayer = Field(default=DataLayer.GRAPH_DATA)

# G. Analytical Analysis Results
from enum import Enum

class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"

class ResolutionResult(BaseModel):
    status: ResolutionStatus
    resolved_company_id: Optional[str] = None
    resolved_company_name: Optional[str] = None
    candidates: List[Dict[str, Any]] = Field(default_factory=list, description="List of ambiguous candidates if AMBIGUOUS")
    reason: Optional[str] = None

class ExposureStatus(str, Enum):
    RESOLVED = "RESOLVED"
    NO_GRAPH_EXPOSURE = "NO_GRAPH_EXPOSURE"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"

class ExposureResult(BaseModel):
    focal_company_id: Optional[str] = None
    status: ExposureStatus
    paths: List[SupplierPath] = Field(default_factory=list)
    tier_groups: Dict[int, List[str]] = Field(default_factory=dict, description="Map of Tier depth to Company IDs")
    max_depth_observed: int = 0
    path_count: int = 0

# H. Risk result
class RiskResult(BaseModel):
    focal_company_id: str
    focal_company_name: Optional[str] = None
    supplier_id: str
    supplier_name: Optional[str] = None
    tier: int
    score: float = Field(ge=0.0, le=1.0, description="Risk score from deterministic calculation")
    risk_level: str = Field(description="E.g., HIGH, MEDIUM, LOW based on deterministic thresholds")
    raw_features: Dict[str, float] = Field(default_factory=dict)
    normalized_features: Dict[str, float] = Field(default_factory=dict)
    feature_weights: Dict[str, float] = Field(default_factory=dict)
    feature_contributions: Dict[str, float] = Field(default_factory=dict)
    formula_version: str
    reasons: List[str] = Field(default_factory=list)
    uncertainty: Optional[str] = None
    provenance: DataLayer = Field(default=DataLayer.DETERMINISTIC_RESULT)

# H. Recommendation
class Recommendation(BaseModel):
    recommendation_id: str
    action: str
    target_supplier_id: str
    risk_context: str
    reasons: List[str]
    evidence_references: List[str] = Field(description="List of Evidence IDs")
    uncertainty: str
    investigation_next_steps: List[str] = Field(default_factory=list)
    layer: DataLayer = Field(default=DataLayer.RECOMMENDATION)

# J. Alternative supplier
class AlternativeSupplier(BaseModel):
    candidate_id: str
    candidate_name: str
    product_or_material: str
    evidence_references: List[str] = Field(default_factory=list)
    evidence_status: EvidenceStatus = Field(default=EvidenceStatus.UNVERIFIED)
    graph_presence: bool = Field(description="Is the candidate already in our canonical graph?")
    current_exposure_state: Optional[str] = None
    ranking_score: float = Field(default=0.0)
    uncertainty: str

# K. Visualization Payload
class VisualNode(BaseModel):
    id: str
    label: str
    tier: Optional[int] = None
    is_focal: bool = False
    is_candidate: bool = False
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    role: Optional[str] = None # e.g., "supplier", "focal_company", "alternative_candidate"

class VisualEdge(BaseModel):
    source: str
    target: str
    relationship_type: str
    is_disrupted: bool = False
    is_alternative: bool = False

class GraphVisualizationPayload(BaseModel):
    nodes: List[VisualNode] = Field(default_factory=list)
    edges: List[VisualEdge] = Field(default_factory=list)
    focal_company_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# L. Early Warning / Temporal Vulnerability
class VulnerabilityIndicator(BaseModel):
    name: str
    description: str
    current_value: float
    baseline_value: Optional[float] = None
    trend: str = "UNKNOWN"
    status: str = Field(description="STABLE, WATCH, ELEVATED, HIGH VULNERABILITY")
    reason: str

class EarlyWarningResult(BaseModel):
    focal_company_id: str
    material_or_category: Optional[str] = None
    indicators: List[VulnerabilityIndicator] = Field(default_factory=list)
    overall_status: str = "STABLE"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
