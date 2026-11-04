import logging
from typing import List, Optional
from pydantic import BaseModel, Field
import json
import uuid

from scdm.llm.client import LLMClient
from scdm.retrieval.search import SearchProvider
from scdm.analysis.resolution import EntityResolver
from scdm.domain.schemas import EvidenceClaim, ResolutionStatus
from scdm.domain.constants import DataLayer, EvidenceStatus
from scdm.llm.client import LLMQuotaExceededError

logger = logging.getLogger(__name__)

# Schema for LLM extraction
class ExtractedProductClaim(BaseModel):
    supplier_name: str = Field(description="Name of the supplier company mentioned")
    product_or_material: str = Field(description="The product, material, or component they supply")
    evidence_snippet: str = Field(description="The exact quote from the text supporting this claim")
    confidence: str = Field(description="High, Medium, or Low confidence based on the text")

class ExtractedProductClaims(BaseModel):
    claims: List[ExtractedProductClaim] = Field(default_factory=list)

PRODUCT_PROMPT = """
You are a supply chain intelligence analyst.
Analyze the following search results to identify which companies manufacture or supply a specific product or material.

Target Product/Material: {material}
Context: {context}

Extract any explicit claims that a company supplies or manufactures this material.
Do NOT invent or assume relationships if the text does not explicitly state it.
If a company is merely mentioned in the same article but not explicitly linked to the product, DO NOT extract it.

Search Results:
{evidence_text}
"""

class ProductSearchAgent:
    """
    Agent 3: Product Search
    Conducts targeted evidence-grounded search for product/material associations without fabricating taxonomy.
    """
    def __init__(self, llm_client: LLMClient, search_provider: SearchProvider, resolver: EntityResolver):
        self.llm_client = llm_client
        self.search_provider = search_provider
        self.resolver = resolver

    def search_product_context(self, target_material: str, focal_company_name: Optional[str] = None) -> List[EvidenceClaim]:
        """
        Conducts a targeted web search for suppliers of a specific material, extracts claims,
        and links them to known entities.
        """
        # 1. Bounded Retrieval
        query = f'"{target_material}" suppliers manufacturers'
        if focal_company_name:
            query += f' "{focal_company_name}"'
            
        try:
            results = self.search_provider.search(query, max_results=5)
        except Exception as e:
            logger.error(f"Product search retrieval failed: {e}")
            return []
            
        if not results:
            return []
            
        evidence_text = "\n\n".join([f"Source [{r.source_url}]:\n{r.snippet}" for r in results])
        context = focal_company_name if focal_company_name else "General supplier landscape"
        
        prompt = PRODUCT_PROMPT.format(
            material=target_material,
            context=context,
            evidence_text=evidence_text
        )
        
        # 2. LLM Extraction
        try:
            llm_result = self.llm_client.generate_structured(prompt, ExtractedProductClaims, max_retries=0)
            extracted = llm_result.claims
        except LLMQuotaExceededError:
            logger.warning("Product search skipping LLM extraction due to Quota Exhaustion.")
            # Return a special claim that indicates unavailable
            return [EvidenceClaim(
                claim_id=f"claim-{uuid.uuid4().hex[:8]}",
                source_url="quota-exhausted",
                subject="PRODUCT_CONTEXT",
                predicate="STATUS",
                object_val="UNAVAILABLE",
                evidence_text="Gemini quota exhausted, product context enrichment skipped.",
                confidence="High",
                status=EvidenceStatus.UNVERIFIED,
                layer=DataLayer.EVIDENCE
            )]
        except Exception as e:
            logger.error(f"Failed to extract product claims via LLM: {e}")
            return []
            
        final_claims = []
        source_map = {r.source_url: r for r in results}
        
        # 3. Entity Resolution & Grounding
        for c in extracted:
            # Find which URL this came from based on snippet match
            matched_url = results[0].source_url if results else "unknown"
            for r in results:
                if c.supplier_name.lower() in r.snippet.lower():
                    matched_url = r.source_url
                    break
                    
            claim_id = f"claim-{uuid.uuid4().hex[:8]}"
            
            res = self.resolver.resolve_focal_company(c.supplier_name)
            
            if res.status == ResolutionStatus.RESOLVED:
                subject_id = res.resolved_company_id
                subject_name = res.resolved_company_name
                status = EvidenceStatus.VALIDATED_CLAIM
                uncertainty = f"Confidence: {c.confidence}"
            elif res.status == ResolutionStatus.AMBIGUOUS:
                subject_id = f"unresolved-{c.supplier_name}"
                subject_name = c.supplier_name
                status = EvidenceStatus.REVIEW_NEEDED
                uncertainty = f"Confidence: {c.confidence} | AMBIGUOUS GRAPH MATCH"
            else:
                subject_id = f"unresolved-{c.supplier_name}"
                subject_name = c.supplier_name
                status = EvidenceStatus.REVIEW_NEEDED
                uncertainty = f"Confidence: {c.confidence} | UNKNOWN TO GRAPH"
                
            claim = EvidenceClaim(
                claim_id=claim_id,
                subject_id=subject_id,
                subject_name=subject_name,
                predicate="SUPPLIES_PRODUCT",
                object_value=c.product_or_material,
                claim_text=c.evidence_snippet,
                sources=[source_map.get(matched_url, results[0]) if results else EvidenceSource(source_url=matched_url)],
                status=status,
                provenance=DataLayer.EXTERNAL_EVIDENCE,
                uncertainty=uncertainty
            )
            final_claims.append(claim)
            
        return final_claims
