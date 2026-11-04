import pytest
import pandas as pd
from scdm.data.normalization import normalize_companies, normalize_relationships
from scdm.data.validation import validate_endpoints
from scdm.domain.constants import RelationshipType

def test_missing_and_duplicate_companies():
    # Duplicate names with distinct IDs, missing values
    df = pd.DataFrame({
        "company_id": ["111", "222", "333", "nan"],
        "company_name": ["Alpha Corp", "Alpha Corp", None, "Ghost Corp"],
        "country_region": ["US", None, "UK", "Unknown"]
    })
    meta = {"source_company_id": "999", "source_company_name": "Focal Corp"}
    
    canonical, focal = normalize_companies([(df, meta)])
    
    # Focal corp is added + 3 valid counterparties
    assert len(focal) == 1
    assert len(canonical) == 4
    
    # ID 111 and 222 have the same name but distinct IDs
    c111 = next(c for c in canonical if c.company_id == "111")
    c222 = next(c for c in canonical if c.company_id == "222")
    c333 = next(c for c in canonical if c.company_id == "333")
    
    assert c111.company_name == "Alpha Corp"
    assert c222.company_name == "Alpha Corp"
    assert c333.company_name is None
    
    # 'nan' company should be skipped
    assert not any(c.company_id == "nan" for c in canonical)

def test_relationship_directions_and_confidence():
    df = pd.DataFrame({
        "company_id": ["111", "222"],
        "relationship": ["Supplier", "Customer"],
        "confidence_pct": [0.99, "85"]
    })
    meta = {"source_company_id": "999"}
    
    rels, rejected = normalize_relationships([(df, meta)])
    assert len(rels) == 2
    assert len(rejected) == 0
    
    sup = next(r for r in rels if r.start_id == "111")
    assert sup.relationship_type == RelationshipType.SUPPLIES
    assert sup.end_id == "999"
    assert sup.confidence == 99.0
    
    cust = next(r for r in rels if r.end_id == "222")
    assert cust.relationship_type == RelationshipType.SELLS_TO
    assert cust.start_id == "999"
    assert cust.confidence == 85.0

def test_unsupported_relationships():
    df = pd.DataFrame({
        "company_id": ["111"],
        "relationship": ["Competitor"]
    })
    meta = {"source_company_id": "999", "source_file": "test.xlsx"}
    
    rels, rejected = normalize_relationships([(df, meta)])
    assert len(rels) == 0
    assert len(rejected) == 1
    assert "Unsupported relationship" in rejected[0]["reason"]

def test_exact_duplicates_and_provenance():
    # Two identical rows
    df1 = pd.DataFrame({
        "company_id": ["111", "111"],
        "relationship": ["Supplier", "Supplier"]
    })
    meta1 = {"source_company_id": "999"}
    
    rels1, _ = normalize_relationships([(df1, meta1)])
    assert len(rels1) == 1 # Exact duplicate within same file is collapsed
    
    # Same endpoint, different focal company (semantic duplicate but distinct provenance)
    df2 = pd.DataFrame({
        "company_id": ["111"],
        "relationship": ["Customer"]  # Focal2 sells to 111 (Start: Focal2, End: 111)
    })
    meta2 = {"source_company_id": "888"}
    
    rels2, _ = normalize_relationships([(df1, meta1), (df2, meta2)])
    assert len(rels2) == 2 # Preserved distinct provenance

def test_orphan_endpoints():
    df = pd.DataFrame({
        "company_id": ["111"], # Exists
        "relationship": ["Supplier"]
    })
    meta = {"source_company_id": "999"} # 999 is missing from canonical companies list for this test
    
    rels, _ = normalize_relationships([(df, meta)])
    
    # Mock a canonical company list that DOES NOT include 999
    from scdm.domain.schemas import Company
    companies = [Company(company_id="111", company_name="Exists")]
    
    valid_rels, orphans = validate_endpoints(rels, companies)
    assert len(valid_rels) == 0
    assert len(orphans) == 1
    assert orphans[0]["reason"] == "Orphan endpoint"
