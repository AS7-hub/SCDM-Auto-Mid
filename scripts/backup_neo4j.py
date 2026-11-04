import json
import os
from pathlib import Path
from neo4j import GraphDatabase
from scdm.core.config import config

def backup_neo4j():
    base_dir = Path(__file__).resolve().parent.parent
    backup_dir = base_dir / "output" / "backup"
    os.makedirs(backup_dir, exist_ok=True)
    
    nodes_file = backup_dir / "snapshot_nodes.json"
    rels_file = backup_dir / "snapshot_rels.json"
    
    password = config.neo4j_password or "password"
    driver = GraphDatabase.driver(
        config.neo4j_uri, 
        auth=(config.neo4j_username, password)
    )
    
    nodes_data = []
    rels_data = []
    
    with driver.session() as session:
        # Get nodes
        result = session.run("MATCH (n) RETURN elementId(n) as id, labels(n) as labels, properties(n) as props")
        for record in result:
            nodes_data.append({
                "id": record["id"],
                "labels": record["labels"],
                "properties": record["props"]
            })
            
        # Get relationships
        result = session.run("MATCH (a)-[r]->(b) RETURN elementId(a) as start_id, type(r) as type, elementId(b) as end_id, properties(r) as props")
        for record in result:
            rels_data.append({
                "start_id": record["start_id"],
                "type": record["type"],
                "end_id": record["end_id"],
                "properties": record["props"]
            })
            
    driver.close()
    
    with open(nodes_file, 'w', encoding='utf-8') as f:
        json.dump(nodes_data, f, indent=2)
        
    with open(rels_file, 'w', encoding='utf-8') as f:
        json.dump(rels_data, f, indent=2)
        
    print(f"Backup complete. Saved {len(nodes_data)} nodes and {len(rels_data)} relationships.")
    print(f"Nodes saved to: {nodes_file}")
    print(f"Relationships saved to: {rels_file}")

if __name__ == "__main__":
    backup_neo4j()
