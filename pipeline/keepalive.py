from neo4j import GraphDatabase

uri = "neo4j+s://____.databases.neo4j.io"
auth = ("neo4j", "____")

driver = GraphDatabase.driver(uri, auth=auth)

with driver.session() as session:
    session.run("RETURN 1").consume()

print("Pinged Neo4j Aura.")
