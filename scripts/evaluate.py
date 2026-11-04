import time
from neo4j import GraphDatabase
from scdm.core.config import config
from scdm.analysis.resolution import EntityResolver
from scdm.analysis.traversal import GraphTraversal

def evaluate_graph_integrity(driver):
    print("\n--- GRAPH INTEGRITY ---")
    with driver.session() as session:
        nodes = session.run("MATCH (n:Company) RETURN count(n) as c").single()['c']
        rels = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()['c']
        supplies = session.run("MATCH ()-[r:SUPPLIES]->() RETURN count(r) as c").single()['c']
        sells_to = session.run("MATCH ()-[r:SELLS_TO]->() RETURN count(r) as c").single()['c']
        unique_ids = session.run("MATCH (n:Company) RETURN count(distinct n.company_id) as c").single()['c']
        
        print(f"Total Company Nodes: {nodes}")
        print(f"Total Relationships: {rels}")
        print(f"SUPPLIES Relationships: {supplies}")
        print(f"SELLS_TO Relationships: {sells_to}")
        print(f"Unique Company IDs: {unique_ids}")
        if nodes != unique_ids:
            print("WARNING: Duplicate company_id detected!")
        else:
            print("No duplicate company IDs.")

def evaluate_resolution():
    print("\n--- ENTITY RESOLUTION ---")
    resolver = EntityResolver(config.neo4j_uri, config.neo4j_username, config.neo4j_password)
    
    test_cases = [
        "Microsoft Corporation",
        "Microsoft",
        "Intel Corp",
        "NonExistentCorp123"
    ]
    
    start = time.time()
    for case in test_cases:
        res = resolver.resolve_focal_company(case)
        print(f"Query: '{case}' -> Status: {res.status.value}, Resolved ID: {res.resolved_company_id}")
    duration = time.time() - start
    print(f"Total resolution time for {len(test_cases)} queries: {duration:.3f}s")

def evaluate_traversal():
    print("\n--- GRAPH TRAVERSAL ---")
    resolver = EntityResolver(config.neo4j_uri, config.neo4j_username, config.neo4j_password)
    traversal = GraphTraversal(config.neo4j_uri, config.neo4j_username, config.neo4j_password)
    
    # Resolve Microsoft to get ID
    ms_res = resolver.resolve_focal_company("Microsoft Corporation")
    if ms_res.status.value != "RESOLVED":
        print("Could not resolve Microsoft for traversal test.")
        return
        
    ms_id = ms_res.resolved_company_id
    
    start = time.time()
    exposure = traversal.get_upstream_exposure(ms_id, max_depth=3)
    duration = time.time() - start
    
    print(f"Focal Company: {ms_id}")
    print(f"Exposure Paths Found: {exposure.path_count}")
    print(f"Max Depth: {exposure.max_depth_observed}")
    print(f"Tier 1 Suppliers: {len(exposure.tier_groups.get(1, []))}")
    print(f"Tier 2 Suppliers: {len(exposure.tier_groups.get(2, []))}")
    print(f"Tier 3 Suppliers: {len(exposure.tier_groups.get(3, []))}")
    print(f"Traversal Runtime: {duration:.3f}s")

if __name__ == "__main__":
    driver = GraphDatabase.driver(config.neo4j_uri, auth=(config.neo4j_username, config.neo4j_password))
    try:
        evaluate_graph_integrity(driver)
        evaluate_resolution()
        evaluate_traversal()
    finally:
        driver.close()
