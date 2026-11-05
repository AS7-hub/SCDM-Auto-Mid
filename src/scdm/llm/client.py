import logging
import json
from typing import TypeVar, Type, Any, Optional
from pydantic import BaseModel, ValidationError
from google import genai
from google.genai import types

from scdm.core.config import config

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class LLMBudgetExceededError(Exception):
    pass

class LLMQuotaExceededError(Exception):
    pass

class LLMClient:
    def __init__(self, budget: int = 3):
        # We handle case where api_key might be missing gracefully in MOCK mode
        api_key = config.gemini_api_key if config.gemini_api_key else "dummy_key"
        self.client = genai.Client(api_key=api_key)
        self.model = config.gemini_model
        self.budget = budget
        self.calls_attempted = 0
        self.calls_successful = 0
        self.cache_hits = 0
        
    def get_telemetry(self) -> dict:
        return {
            "model": self.model,
            "budget_limit": self.budget,
            "calls_attempted": self.calls_attempted,
            "calls_successful": self.calls_successful,
            "cache_hits": self.cache_hits,
            "budget_remaining": max(0, self.budget - self.calls_successful)
        }

    def get_budget_status(self) -> dict:
        return {
            "budget": self.budget,
            "attempted": self.calls_attempted,
            "successful": self.calls_successful,
            "remaining": max(0, self.budget - self.calls_successful)
        }

    def generate_structured(self, prompt: str, schema: Type[T], max_retries: int = 1) -> T:
        """
        Generates structured output strictly adhering to the Pydantic schema.
        Includes bounded retries for malformed JSON or transient errors.
        """
        retries = 0
        last_error = None
        
        while retries <= max_retries:
            self.calls_attempted += 1
            if self.calls_successful >= self.budget:
                logger.error(f"LLM Budget Exceeded. Attempted: {self.calls_attempted}, Limit: {self.budget}")
                raise LLMBudgetExceededError(f"Budget of {self.budget} LLM calls exceeded.")
                
            logger.info(f"Generating structured output using {self.model} (Call {self.calls_successful + 1}/{self.budget})")
            try:
                def remove_additional_properties(d):
                    if isinstance(d, dict):
                        d.pop("additionalProperties", None)
                        for k, v in d.items():
                            remove_additional_properties(v)
                    elif isinstance(d, list):
                        for item in d:
                            remove_additional_properties(item)

                schema_dict = schema.model_json_schema()
                remove_additional_properties(schema_dict)

                # Ask model for JSON
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema_dict,
                        temperature=0.0
                    ),
                )
                
                if not response.text:
                    raise ValueError("Model returned empty text.")
                
                # Parse to schema
                result = schema.model_validate_json(response.text)
                self.calls_successful += 1
                return result
                
            except ValidationError as ve:
                logger.warning(f"Schema validation failed on attempt {retries + 1}: {ve}")
                last_error = ve
            except Exception as e:
                # Do not retry if we hit Quota errors
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    logger.error(f"LLM Quota Exceeded (429): {e}")
                    raise LLMQuotaExceededError(f"Quota exceeded: {e}")
                if "503" in str(e) or "UNAVAILABLE" in str(e) or "high demand" in str(e).lower():
                    # Fallback to stable fast model if current model experiences high demand spikes
                    fallback_model = "gemini-2.5-flash"
                    if self.model != fallback_model:
                        logger.warning(f"Model {self.model} hit 503 high demand. Falling back to {fallback_model} for attempt {retries + 1}...")
                        self.model = fallback_model
                logger.warning(f"LLM call failed on attempt {retries + 1}: {e}")
                last_error = e
                
            retries += 1
            
        logger.error(f"Failed to generate structured output after {retries} attempts. Last error: {last_error}")
        raise last_error
