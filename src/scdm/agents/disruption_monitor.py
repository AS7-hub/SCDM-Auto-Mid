import logging
import uuid
from typing import List, Dict, Any, Optional

from scdm.llm.client import LLMClient, LLMQuotaExceededError
from scdm.domain.schemas import DisruptionEvent, EvidenceSource
from scdm.domain.constants import DataLayer

logger = logging.getLogger(__name__)

DISRUPTION_PROMPT = """
You are an expert supply chain intelligence analyst. Your task is to extract a structured DisruptionEvent from the user query and the provided search evidence.

Rules:
1. DO NOT invent dates, materials, or affected entities. If it is not explicitly stated in the query or evidence, output "UNKNOWN" or leave the list empty.
2. The `affected_material` must be a specific raw material or component (e.g., "palladium", "semiconductors").
3. Summarize the description neutrally and accurately based ONLY on evidence.
4. Set `uncertainty` if there is conflicting information or lack of hard facts.

User Query: {query}

Evidence:
{evidence_text}

Extract the disruption event based on the above information strictly conforming to the JSON schema provided.
"""

class DisruptionMonitorAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def extract_event(self, query: str, evidence: List[EvidenceSource]) -> DisruptionEvent:
        if not evidence:
            evidence_text = "No evidence retrieved."
        else:
            evidence_text = "\n\n".join([f"Title: {e.title}\nURL: {e.source_url}\nSnippet: {e.snippet}" for e in evidence])

        prompt = DISRUPTION_PROMPT.format(query=query, evidence_text=evidence_text)
        
        try:
            # We ask the LLM Client to extract to DisruptionEvent schema
            event = self.llm_client.generate_structured(prompt, DisruptionEvent, max_retries=1)
            # Ensure identifiers and layers are stamped safely deterministic
            event.event_id = str(uuid.uuid4())
            event.layer = DataLayer.LLM_INTERPRETATION
            return event
        except LLMQuotaExceededError:
            logger.error("Failed to extract disruption event due to Quota Exhaustion.")
            return DisruptionEvent(
                event_id=str(uuid.uuid4()),
                disruption_type="QUOTA_EXHAUSTED",
                description="Gemini quota exhausted. Cannot parse natural language disruption context.",
                uncertainty="HIGH - QUOTA EXHAUSTED",
                layer=DataLayer.LLM_INTERPRETATION
            )
        except Exception as e:
            logger.error(f"Failed to extract disruption event: {e}")
            # Fallback for structured pipeline: return an explicit unknown event rather than crashing workflow
            return DisruptionEvent(
                event_id=str(uuid.uuid4()),
                disruption_type="UNKNOWN",
                description=f"Failed to parse disruption due to LLM error: {str(e)}",
                uncertainty="HIGH - LLM ERROR",
                layer=DataLayer.LLM_INTERPRETATION
            )
