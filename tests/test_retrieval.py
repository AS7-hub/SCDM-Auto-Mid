import pytest
from unittest.mock import patch, MagicMock

from scdm.retrieval.search import DuckDuckGoSearchProvider
from scdm.domain.constants import EvidenceStatus

def test_retrieval_caching():
    provider = DuckDuckGoSearchProvider()
    
    with patch('scdm.retrieval.search.DDGS') as mock_ddgs:
        # Mock instance
        mock_instance = MagicMock()
        mock_ddgs.return_value.__enter__.return_value = mock_instance
        mock_instance.text.return_value = [
            {"href": "https://example.com/1", "title": "Test 1", "body": "Snippet 1"}
        ]
        
        # First call, should hit mock
        res1 = provider.search("test query")
        assert len(res1) == 1
        assert res1[0].source_url == "https://example.com/1"
        assert mock_instance.text.call_count == 1
        
        # Second call, should hit cache
        res2 = provider.search("test query")
        assert len(res2) == 1
        assert res2[0].source_url == "https://example.com/1"
        assert mock_instance.text.call_count == 1 # Still 1!

def test_retrieval_deduplication():
    provider = DuckDuckGoSearchProvider()
    
    with patch('scdm.retrieval.search.DDGS') as mock_ddgs:
        mock_instance = MagicMock()
        mock_ddgs.return_value.__enter__.return_value = mock_instance
        # Return same URL but with different hash fragment
        mock_instance.text.return_value = [
            {"href": "https://example.com/article", "title": "Test A"},
            {"href": "https://example.com/article#comments", "title": "Test B"},
            {"href": "https://example.com/other", "title": "Test C"}
        ]
        
        res = provider.search("dedup query")
        # Should only return 2 unique items
        assert len(res) == 2
        assert res[0].source_url == "https://example.com/article"
        assert res[1].source_url == "https://example.com/other"

def test_retrieval_error_handling():
    provider = DuckDuckGoSearchProvider(max_retries=1)
    
    with patch('scdm.retrieval.search.DDGS') as mock_ddgs:
        mock_instance = MagicMock()
        mock_ddgs.return_value.__enter__.return_value = mock_instance
        # Force exception
        mock_instance.text.side_effect = Exception("DDG Timeout")
        
        res = provider.search("error query")
        
        assert len(res) == 1
        assert res[0].status == EvidenceStatus.SEARCH_ERROR
        assert res[0].provider == "DuckDuckGo"
        # Since retries is 1, it should have called text twice (initial + 1 retry)
        assert mock_instance.text.call_count == 2

def test_retrieval_empty_results():
    provider = DuckDuckGoSearchProvider()
    
    with patch('scdm.retrieval.search.DDGS') as mock_ddgs:
        mock_instance = MagicMock()
        mock_ddgs.return_value.__enter__.return_value = mock_instance
        # Empty list
        mock_instance.text.return_value = []
        
        res = provider.search("empty query")
        
        assert len(res) == 1
        assert res[0].status == EvidenceStatus.NO_SEARCH_RESULTS
        assert res[0].provider == "DuckDuckGo"
