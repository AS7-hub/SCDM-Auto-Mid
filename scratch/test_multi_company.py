import os
import sys

from scdm.core.config import config
from scdm.analysis.resolution import EntityResolver
from scdm.analysis.traversal import GraphTraversal
from scdm.analysis.risk_engine import RiskEngine
from scdm.domain.schemas import ExposureResult

def main():
    print("============================================================")
    print("DETERMINISTIC MULTI-COMPANY INTEGRATION HARNESS")
    print("============================================================")
    
    resolver = EntityResolver(config.neo4j_uri, config.neo4j_username, config.neo4j_password)
    traversal = GraphTraversal(config.neo4j_uri, config.neo4j_username, config.neo4j_password)
    risk_engine = RiskEngine()
    
    test_companies = [
        "BMW",
        "BMW AG",
        "BYD",
        "Ford",
        "Ford Motor",
        "Ford Motor Co",
        "Honda",
        "Kia",
        "Mercedes-Benz",
        "Mitsubishi",
        "Tata",
        "Volkswagen",
        "Toyota",
        "Tesla",
        "FakeCompanyThatDoesNotExist123"
    ]
    
    print(f"{'Input':<25} | {'Status':<12} | {'Resolved ID':<15} | {'T1':<4} | {'T2':<4} | {'T3':<4} | {'Total':<5} | {'Risk Count'}")
    print("-" * 100)
    
    for company in test_companies:
        res = resolver.resolve_focal_company(company)
        status = res.status.name
        res_id = res.resolved_company_id if res.resolved_company_id else "None"
        
        t1, t2, t3, total = 0, 0, 0, 0
        risk_count = 0
        
        if status == "RESOLVED":
            exposure = traversal.get_upstream_exposure(res_id, max_depth=3)
            if exposure:
                t1 = len(exposure.tier_groups.get(1, []))
                t2 = len(exposure.tier_groups.get(2, []))
                t3 = len(exposure.tier_groups.get(3, []))
                total = t1 + t2 + t3
                
                exp_res = ExposureResult(
                    status="RESOLVED",
                    focal_company_id=res_id,
                    paths=exposure.paths
                )
                rrs = risk_engine.calculate_risk(exp_res)
                risk_count = len(rrs) if rrs else 0
        
        print(f"{company:<25} | {status:<12} | {res_id:<15} | {t1:<4} | {t2:<4} | {t3:<4} | {total:<5} | {risk_count}")

if __name__ == '__main__':
    main()
