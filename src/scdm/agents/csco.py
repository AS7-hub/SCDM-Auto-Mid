import logging
import uuid
from typing import List, Dict, Any

from scdm.llm.client import LLMClient, LLMQuotaExceededError
from scdm.domain.schemas import DisruptionEvent, RiskResult, Recommendation, EvidenceSource
from scdm.domain.constants import DataLayer

logger = logging.getLogger(__name__)

CSCO_PROMPT = """
You are the Chief Supply Chain Officer (CSCO) decision agent. Your task is to recommend an operational posture based on the DETERMINISTIC RISK SCORE and retrieved evidence.

Rules:
1. DO NOT calculate or modify the risk score. The deterministic `RiskResult` is authoritative.
2. If Risk Level is HIGH -> recommend "REPLACE" or "ALTERNATIVE SOURCING".
3. If Risk Level is MEDIUM -> recommend "INCREASED MONITORING".
4. If Risk Level is LOW -> recommend "STANDARD OPERATIONS".
5. Summarize the risk and synthesize evidence. DO NOT invent capacity, prices, lead times, or exact financial loss.
6. If required information is unavailable, explicitly state uncertainty.

Disruption Event:
{disruption}

Deterministic Risk Profile:
{risk_result}

Supporting Evidence:
{evidence_text}

Output a strictly conforming Recommendation JSON.
"""

class CSCOAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def generate_recommendation(
        self,
        risk: RiskResult,
        disruption: DisruptionEvent,
        evidence: List[EvidenceSource]
    ) -> Recommendation:
        
        evidence_text = "No evidence retrieved."
        if evidence:
            evidence_text = "\n\n".join([f"Title: {e.title}\nSnippet: {e.snippet}" for e in evidence])

        disruption_info = disruption.model_dump_json(include={'disruption_type', 'description', 'affected_material', 'uncertainty'})
        risk_info = risk.model_dump_json(include={'supplier_id', 'tier', 'score', 'risk_level'})
        
        prompt = CSCO_PROMPT.format(
            disruption=disruption_info,
            risk_result=risk_info,
            evidence_text=evidence_text
        )
        
        try:
            rec = self.llm_client.generate_structured(prompt, Recommendation, max_retries=1)
            rec.recommendation_id = str(uuid.uuid4())
            rec.target_supplier_id = risk.supplier_id
            rec.layer = DataLayer.RECOMMENDATION
            return rec
        except LLMQuotaExceededError:
            logger.error("Failed to generate CSCO recommendation: Quota exceeded.")
            
            # Map fallback action deterministically
            action = "STANDARD OPERATIONS"
            if risk.risk_level == "HIGH":
                action = "ALTERNATIVE SOURCING"
            elif risk.risk_level == "MEDIUM":
                action = "INCREASED MONITORING"
                
            return Recommendation(
                recommendation_id=str(uuid.uuid4()),
                action=action,
                target_supplier_id=risk.supplier_id,
                risk_context=f"Score: {risk.score}, Level: {risk.risk_level}",
                reasons=["Fallback recommendation triggered due to Quota Exhaustion."],
                evidence_references=[],
                uncertainty="HIGH - QUOTA EXHAUSTED",
                layer=DataLayer.RECOMMENDATION
            )
        except Exception as e:
            logger.error(f"Failed to generate CSCO recommendation: {e}")
            
            # Map fallback action deterministically
            action = "STANDARD OPERATIONS"
            if risk.risk_level == "HIGH":
                action = "ALTERNATIVE SOURCING"
            elif risk.risk_level == "MEDIUM":
                action = "INCREASED MONITORING"
                
            return Recommendation(
                recommendation_id=str(uuid.uuid4()),
                action=action,
                target_supplier_id=risk.supplier_id,
                risk_context=f"Score: {risk.score}, Level: {risk.risk_level}",
                reasons=[f"Fallback recommendation triggered due to LLM error: {str(e)}"],
                evidence_references=[],
                uncertainty="HIGH - LLM ERROR",
                layer=DataLayer.RECOMMENDATION
            )
