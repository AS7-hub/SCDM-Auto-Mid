from scdm.core.config import config
from scdm.llm.client import LLMClient
from neo4j import GraphDatabase
from pydantic import BaseModel

class Dummy(BaseModel):
    status: str

print("Verifying Gemini...")
client = LLMClient()
res = client.generate_structured('Reply with status OK', Dummy)
print('Gemini:', res.status)

print("Verifying Neo4j...")
driver = GraphDatabase.driver(config.neo4j_uri, auth=(config.neo4j_username, config.neo4j_password))
with driver.session() as session:
    nodes = session.run("MATCH (n:Company) RETURN count(n) as c").single()['c']
    rels = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()['c']
    supplies = session.run("MATCH ()-[r:SUPPLIES]->() RETURN count(r) as c").single()['c']
    sells_to = session.run("MATCH ()-[r:SELLS_TO]->() RETURN count(r) as c").single()['c']
    print(f"Nodes: {nodes}, Rels: {rels}, SUPPLIES: {supplies}, SELLS_TO: {sells_to}")
driver.close()
