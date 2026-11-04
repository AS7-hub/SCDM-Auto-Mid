import logging
from typing import List, Protocol
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

from ddgs import DDGS

from scdm.domain.schemas import EvidenceSource
from scdm.domain.constants import EvidenceStatus, DataLayer

logger = logging.getLogger(__name__)

class SearchProvider(Protocol):
    def search(self, query: str, max_results: int = 5) -> List[EvidenceSource]:
        ...

class DuckDuckGoSearchProvider(SearchProvider):
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.cache = {} # Map of canonical_query -> List[EvidenceSource]

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            # Normalization: Strip tracking params, hash fragments, etc.
            # For strict canonicalization we drop everything after path, but some sites rely on query.
            # We'll drop query for common tracking, or just drop fragment.
            # Let's keep it simple: drop fragment, keep path.
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))
        except Exception:
            return url

    def search(self, query: str, max_results: int = 5) -> List[EvidenceSource]:
        if not query or not query.strip():
            return []
            
        cache_key = f"{query.strip().lower()}::{max_results}"
        if cache_key in self.cache:
            logger.info(f"Search cache hit for '{query}'")
            return self.cache[cache_key]

        results = []
        retries = 0
        while retries <= self.max_retries:
            try:
                with DDGS() as ddgs:
                    ddg_results = list(ddgs.text(query, max_results=max_results))
                
                seen_urls = set()
                for r in ddg_results:
                    url = r.get("href", "")
                    norm_url = self._normalize_url(url)
                    
                    if not norm_url or norm_url in seen_urls:
                        continue
                    seen_urls.add(norm_url)
                    
                    source = EvidenceSource(
                        source_url=url,
                        title=r.get("title", ""),
                        snippet=r.get("body", ""),
                        retrieved_timestamp=datetime.now(timezone.utc),
                        search_query=query,
                        provider="DuckDuckGo",
                        status=EvidenceStatus.SEARCH_RESULT_FOUND,
                        provenance=DataLayer.EXTERNAL_EVIDENCE
                    )
                    results.append(source)
                
                if not results:
                    err_source = EvidenceSource(
                        search_query=query,
                        provider="DuckDuckGo",
                        status=EvidenceStatus.NO_SEARCH_RESULTS,
                        retrieved_timestamp=datetime.now(timezone.utc),
                        provenance=DataLayer.EXTERNAL_EVIDENCE
                    )
                    self.cache[cache_key] = [err_source]
                    return [err_source]
                
                self.cache[cache_key] = results
                return results

            except Exception as e:
                logger.warning(f"DuckDuckGo search failed (attempt {retries + 1}): {e}")
                retries += 1
                
        # If we exhausted retries
        err_source = EvidenceSource(
            search_query=query,
            provider="DuckDuckGo",
            status=EvidenceStatus.SEARCH_ERROR,
            retrieved_timestamp=datetime.now(timezone.utc),
            provenance=DataLayer.EXTERNAL_EVIDENCE
        )
        return [err_source]
