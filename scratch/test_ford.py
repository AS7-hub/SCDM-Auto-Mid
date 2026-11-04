import sys
import os

from scdm.core.config import config
from neo4j import GraphDatabase
from scdm.analysis.resolution import EntityResolver
from scdm.analysis.traversal import GraphTraversal

def main():
    print("==================================================")
    print("2. QUERY THE ACTUAL NEO4J GRAPH DIRECTLY")
    print("==================================================")
    driver = GraphDatabase.driver(config.neo4j_uri, auth=(config.neo4j_username, config.neo4j_password))
    with driver.session() as session:
        res = session.run("MATCH (c:Company) WHERE toLower(toString(c.company_name)) CONTAINS 'ford' OR toLower(toString(c.company_id)) CONTAINS 'ford' RETURN c.company_id, c.company_name ORDER BY c.company_name LIMIT 30")
        for r in res:
            print(f"{r['c.company_id']} : {r['c.company_name']}")

    print("\n==================================================")
    print("3. TEST ENTITY RESOLUTION DIRECTLY")
    print("==================================================")
    resolver = EntityResolver(config.neo4j_uri, config.neo4j_username, config.neo4j_password)
    print("Resolution for 'Ford Motor':")
    res1 = resolver.resolve_focal_company("Ford Motor")
    print(res1)
    
    print("\nResolution for 'Ford Motor Company':")
    res2 = resolver.resolve_focal_company("Ford Motor Company")
    print(res2)

    print("\nResolution for 'Ford Motor Co':")
    res3 = resolver.resolve_focal_company("Ford Motor Co")
    print(res3)

    print("\n==================================================")
    print("4. TEST GRAPH TRAVERSAL DIRECTLY")
    print("==================================================")
    traversal = GraphTraversal(config.neo4j_uri, config.neo4j_username, config.neo4j_password)
    
    # Try with the ID for Ford Motor Co (which we know is 4295903068 from our previous query in mind)
    # Let's get the ID if resolved, otherwise default to "4295903068"
    canonical_id = None
    if res3 and hasattr(res3, "status") and res3.status.name == "RESOLVED":
        canonical_id = res3.resolved_company_id
    else:
        canonical_id = "4295903068"
        
    print(f"Testing traversal with canonical_id: {canonical_id}")
    exposure = traversal.get_upstream_exposure(canonical_id, max_depth=3)
    if exposure:
        t1 = exposure.tier_groups.get(1, [])
        t2 = exposure.tier_groups.get(2, [])
        t3 = exposure.tier_groups.get(3, [])
        print(f"Tier 1 count: {len(t1)}")
        print(f"Tier 2 count: {len(t2)}")
        print(f"Tier 3 count: {len(t3)}")
        print(f"total exposure count: {len(t1) + len(t2) + len(t3)}")
    else:
        print("No exposure returned.")

if __name__ == '__main__':
    main()
