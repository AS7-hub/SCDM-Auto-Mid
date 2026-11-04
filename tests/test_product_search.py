import pytest
from unittest.mock import MagicMock
from scdm.agents.product_search import ProductSearchAgent, ExtractedProductClaims, ExtractedProductClaim
from scdm.domain.schemas import ResolutionResult, ResolutionStatus, EvidenceSource
from scdm.domain.constants import EvidenceStatus
from scdm.llm.client import LLMClient
from scdm.retrieval.search import SearchProvider
from scdm.analysis.resolution import EntityResolver

def test_product_search_success():
    llm = MagicMock(spec=LLMClient)
    llm.generate_structured.return_value = ExtractedProductClaims(
        claims=[
            ExtractedProductClaim(
                supplier_name="MockSupplier",
                product_or_material="Palladium",
                evidence_snippet="MockSupplier provides Palladium.",
                confidence="High"
            )
        ]
    )
    
    search_provider = MagicMock(spec=SearchProvider)
    search_provider.search.return_value = [
        EvidenceSource(source_url="http://mock.com", title="Mock", snippet="MockSupplier provides Palladium.")
    ]
    
    resolver = MagicMock(spec=EntityResolver)
    resolver.resolve_focal_company.return_value = ResolutionResult(
        status=ResolutionStatus.RESOLVED,
        resolved_company_id="sup-123",
        resolved_company_name="MockSupplier"
    )
    
    agent = ProductSearchAgent(llm, search_provider, resolver)
    claims = agent.search_product_context("Palladium")
    
    assert len(claims) == 1
    assert claims[0].subject_id == "sup-123"
    assert claims[0].subject_name == "MockSupplier"
    assert claims[0].object_value == "Palladium"
    assert claims[0].status == EvidenceStatus.VALIDATED_CLAIM
    assert claims[0].sources[0].source_url == "http://mock.com"

def test_product_search_ambiguous_resolution():
    llm = MagicMock(spec=LLMClient)
    llm.generate_structured.return_value = ExtractedProductClaims(
        claims=[
            ExtractedProductClaim(
                supplier_name="AmbiguousCorp",
                product_or_material="Palladium",
                evidence_snippet="test",
                confidence="High"
            )
        ]
    )
    
    search_provider = MagicMock(spec=SearchProvider)
    search_provider.search.return_value = [EvidenceSource(source_url="test", snippet="test")]
    
    resolver = MagicMock(spec=EntityResolver)
    resolver.resolve_focal_company.return_value = ResolutionResult(status=ResolutionStatus.AMBIGUOUS, candidates=[{"name":"1"}])
    
    agent = ProductSearchAgent(llm, search_provider, resolver)
    claims = agent.search_product_context("Palladium")
    
    assert len(claims) == 1
    assert claims[0].status == EvidenceStatus.REVIEW_NEEDED
    assert "AMBIGUOUS" in claims[0].uncertainty

def test_product_search_no_results():
    search_provider = MagicMock(spec=SearchProvider)
    search_provider.search.return_value = []
    agent = ProductSearchAgent(MagicMock(), search_provider, MagicMock())
    claims = agent.search_product_context("Palladium")
    assert len(claims) == 0

def test_product_search_llm_failure():
    llm = MagicMock(spec=LLMClient)
    llm.generate_structured.side_effect = Exception("API error")
    
    search_provider = MagicMock(spec=SearchProvider)
    search_provider.search.return_value = [EvidenceSource(source_url="test", snippet="test")]
    
    agent = ProductSearchAgent(llm, search_provider, MagicMock())
    claims = agent.search_product_context("Palladium")
    assert len(claims) == 0
