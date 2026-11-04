import logging
import uuid
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from scdm.llm.client import LLMClient, LLMQuotaExceededError
from scdm.domain.schemas import DisruptionEvent, EvidenceSource, AlternativeSupplier
from scdm.domain.constants import DataLayer, EvidenceStatus

logger = logging.getLogger(__name__)

# Temporary schema for LLM extraction before deterministic enrichment
class ExtractedCandidate(BaseModel):
    candidate_name: str
    product_or_material: str
    reasons: str = Field(description="Why is this a valid alternative according to the evidence?")
    confidence_in_evidence: str = Field(description="High, Medium, Low based on text")

class ExtractedCandidates(BaseModel):
    candidates: List[ExtractedCandidate] = Field(default_factory=list)

ALTERNATIVE_PROMPT = """
You are a supply chain sourcing agent. Your task is to identify plausible alternative suppliers for the affected material based SOLELY on the provided evidence.

Rules:
1. ONLY extract candidates explicitly named in the evidence.
2. DO NOT invent capacity, price, delivery time, or contractual feasibility.
3. If no clear alternative is mentioned, return an empty list.
4. Extract the exact company name.

Affected Material:
{material}

Disruption Context:
{disruption_desc}

Evidence:
{evidence_text}

Extract candidates adhering to the JSON schema.
"""

from scdm.analysis.resolution import EntityResolver
from scdm.analysis.traversal import GraphTraversal
from scdm.domain.schemas import ResolutionStatus

class AlternativeSourcingAgent:
    def __init__(self, llm_client: LLMClient, resolver: EntityResolver, traversal: GraphTraversal):
        self.llm_client = llm_client
        self.resolver = resolver
        self.traversal = traversal

    def extract_and_qualify_candidates(self, material: str, disruption_desc: str, evidence: List[EvidenceSource], focal_company_id: str) -> List[AlternativeSupplier]:
        if not evidence:
            return []
            
        evidence_text = "\n\n".join([f"Source [{e.source_url}]:\n{e.snippet}" for e in evidence])
        prompt = ALTERNATIVE_PROMPT.format(
            material=material,
            disruption_desc=disruption_desc,
            evidence_text=evidence_text
        )
        
        alternatives = []
        try:
            result = self.llm_client.generate_structured(prompt, ExtractedCandidates, max_retries=1)
            extracted = result.candidates
        except LLMQuotaExceededError:
            logger.error("Failed to extract alternatives: Quota exceeded.")
            extracted = []
        except Exception as e:
            logger.error(f"Failed to extract alternatives: {e}")
            extracted = []
            
        for c in extracted:
            alt = AlternativeSupplier(
                candidate_id=f"alt-{uuid.uuid4().hex[:8]}", # Temporary ID until resolved
                candidate_name=c.candidate_name,
                product_or_material=c.product_or_material,
                evidence_status=EvidenceStatus.EVIDENCE_CANDIDATE,
                evidence_references=[c.reasons],
                uncertainty=f"Evidence Confidence: {c.confidence_in_evidence}",
                graph_presence=False,
                ranking_score=0.0
            )
            
            # Deterministic Entity Resolution
            res = self.resolver.resolve_focal_company(alt.candidate_name)
            
            if res.status.name == "RESOLVED":
                alt.candidate_id = res.resolved_company_id
                alt.candidate_name = res.resolved_company_name
                alt.graph_presence = True
                
                # Deterministic Graph Connectivity
                conn = self.traversal.check_supplier_connectivity(alt.candidate_id, focal_company_id)
                
                base_score = 0.5 # Graph presence
                focal_bonus = 0.0
                if conn["is_connected_to_focal"]:
                    dist = conn["min_distance_to_focal"]
                    focal_bonus = 0.3 + (0.2 / dist) if dist > 0 else 0.5
                    alt.current_exposure_state = f"Connected at distance {dist}"
                    alt.evidence_status = EvidenceStatus.VALIDATED_CLAIM
                else:
                    alt.current_exposure_state = "Not connected to focal company"
                    alt.evidence_status = EvidenceStatus.REVIEW_NEEDED
                    
                global_bonus = min(0.1 * conn["total_downstream_customers"], 0.5)
                
                alt.ranking_score = base_score + focal_bonus + global_bonus
                
            elif res.status == ResolutionStatus.AMBIGUOUS:
                alt.uncertainty += f" | AMBIGUOUS GRAPH MATCH: Multiple candidates found."
                alt.evidence_status = EvidenceStatus.REVIEW_NEEDED
            else:
                alt.uncertainty += f" | NOT FOUND IN GRAPH"
                alt.evidence_status = EvidenceStatus.REVIEW_NEEDED
                
            alternatives.append(alt)
            
        return alternatives
