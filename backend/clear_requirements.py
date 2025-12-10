#!/usr/bin/env python3
"""
Utility to clear all requirements from Neo4j.
"""

from neo4j import GraphDatabase

# Direct configuration (no imports needed)
DEFAULT_URI = "neo4j+s://fa69a4aa.databases.neo4j.io"
DEFAULT_USER = "neo4j"
DEFAULT_PASSWORD = "nHQVCBIQ0fX4ysrTqHJFyfwWhKvsQfwHdxZGS4g7TUM"
DEFAULT_DATABASE = "neo4j"

def clear_requirements():
    """Remove all requirements and their relationships from Neo4j."""
    print("Connecting to Neo4j...")
    driver = GraphDatabase.driver(DEFAULT_URI, auth=(DEFAULT_USER, DEFAULT_PASSWORD))
    
    try:
        with driver.session(database=DEFAULT_DATABASE) as session:
            print("\nDeleting all requirements and relationships...")
            result = session.run("MATCH (n:Requirement) DETACH DELETE n")
            
            # Get deletion statistics
            stats = result.consume().counters
            print(f"\nDeleted:")
            print(f"- {stats.nodes_deleted} nodes")
            print(f"- {stats.relationships_deleted} relationships")
            
    finally:
        driver.close()
        
    print("\nDatabase cleared successfully!")

if __name__ == "__main__":
    clear_requirements()