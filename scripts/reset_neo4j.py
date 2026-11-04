import logging
from neo4j import GraphDatabase
from scdm.core.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_neo4j():
    logger.info("Initializing connection to Neo4j to perform destructive reset.")
    password = config.neo4j_password or "password"
    driver = GraphDatabase.driver(
        config.neo4j_uri, 
        auth=(config.neo4j_username, password)
    )
    
    with driver.session() as session:
        # Verify we are operating on the default database 'neo4j'
        # In Community Edition, we can only write to 'neo4j'
        
        # 1. Drop all constraints
        try:
            res = session.run("SHOW CONSTRAINTS")
            for record in res:
                c_name = record["name"]
                logger.info(f"Dropping constraint: {c_name}")
                session.run(f"DROP CONSTRAINT {c_name}")
        except Exception as e:
            logger.warning(f"Error dropping constraints: {e}")
            
        # 2. Drop all custom indexes (except implicit ones created by constraints)
        try:
            res = session.run("SHOW INDEXES")
            for record in res:
                i_name = record["name"]
                # Skip indexes that are backing constraints or built-in token indexes
                if "constraint" not in record.get("labelsOrTypes", []) and "LOOKUP" not in record.get("type", ""):
                    logger.info(f"Dropping index: {i_name}")
                    try:
                        session.run(f"DROP INDEX {i_name}")
                    except Exception as drop_e:
                        logger.warning(f"Could not drop index {i_name} (might be backed by constraint): {drop_e}")
        except Exception as e:
            logger.warning(f"Error dropping indexes: {e}")
            
        # 3. DETACH DELETE ALL
        logger.info("Executing DETACH DELETE for all nodes...")
        result = session.run("MATCH (n) DETACH DELETE n")
        counters = result.consume().counters
        logger.info(f"Deleted {counters.nodes_deleted} nodes and {counters.relationships_deleted} relationships.")
        
    driver.close()
    logger.info("Neo4j database reset complete.")

if __name__ == "__main__":
    reset_neo4j()
