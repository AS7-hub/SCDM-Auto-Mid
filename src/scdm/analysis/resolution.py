import logging
from typing import Optional, List, Dict, Any
from neo4j import GraphDatabase
import re
from scdm.domain.schemas import ResolutionResult, ResolutionStatus

logger = logging.getLogger(__name__)

class EntityResolver:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def _normalize(self, term: str) -> str:
        # Conservative normalization: lowercasing and stripping whitespace and punctuation
        t = term.strip().lower()
        # Remove common legal suffixes at the end of the string
        # using word boundaries
        suffixes = r'\b(co|inc|llc|ltd|ag|corp|corporation|group|company)\b\.?'
        t = re.sub(suffixes, '', t)
        # Remove commas, periods, dashes
        t = re.sub(r'[,.\-]', ' ', t)
        # Collapse multiple spaces
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def resolve_focal_company(self, query: str) -> ResolutionResult:
        """
        Deterministically resolves a user query to a Company node in Neo4j.
        Hierarchy:
        1. Exact company_id
        2. Exact normalized company_name
        3. Normalized contains match
        """
        if not query or not query.strip():
            return ResolutionResult(
                status=ResolutionStatus.UNRESOLVED,
                reason="Empty query provided."
            )
            
        term = query.strip()
        norm_term = self._normalize(term)

        with self.driver.session() as session:
            # 1. Exact company_id match
            res_id = session.run("MATCH (c:Company {company_id: $id}) RETURN c.company_id as id, c.company_name as name", id=term)
            records_id = list(res_id)
            if len(records_id) == 1:
                return ResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    resolved_company_id=records_id[0]["id"],
                    resolved_company_name=records_id[0]["name"],
                    reason="Matched exact company_id."
                )
                
            # We want to match all nodes that contain or equal the term
            # Neo4j query combining exact and contains on both name and id
            query_str = """
            MATCH (c:Company)
            WHERE c.company_name IS NOT NULL
            WITH c, toLower(toString(c.company_name)) AS raw_name
            WHERE raw_name = $term 
               OR raw_name CONTAINS $term 
               OR raw_name = $norm
               OR raw_name CONTAINS $norm
            RETURN c.company_id as id, c.company_name as name
            """
            res_candidates = session.run(query_str, term=term.lower(), norm=norm_term)
            candidates = list(res_candidates)
            
            # De-duplicate candidates
            seen = {}
            for c in candidates:
                if c["id"] not in seen:
                    seen[c["id"]] = {"id": c["id"], "name": c["name"]}
            
            distinct = list(seen.values())
            
            if len(distinct) == 1:
                # 2. Unambiguous exact or contains match
                return ResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    resolved_company_id=distinct[0]["id"],
                    resolved_company_name=distinct[0]["name"],
                    reason="Resolved via unambiguous name match."
                )
            elif len(distinct) > 1:
                # 3. Ambiguous
                # Wait, if one is an exact match (e.g. Ford Motor Co vs Ford Motor Credit Company LLC),
                # and norm_term strictly equals the exact normalized name of one, pick it!
                exact_matches = []
                for c in distinct:
                    if self._normalize(c["name"]) == norm_term:
                        exact_matches.append(c)
                
                if len(exact_matches) == 1:
                    return ResolutionResult(
                        status=ResolutionStatus.RESOLVED,
                        resolved_company_id=exact_matches[0]["id"],
                        resolved_company_name=exact_matches[0]["name"],
                        reason="Matched exact normalized company_name despite partial ambiguity."
                    )
                else:
                    return ResolutionResult(
                        status=ResolutionStatus.AMBIGUOUS,
                        candidates=distinct,
                        reason=f"Found {len(distinct)} distinct companies matching '{term}'."
                    )
                
        # 4. Unresolved
        return ResolutionResult(
            status=ResolutionStatus.UNRESOLVED,
            reason="No graph node matched the query."
        )
