#!/usr/bin/env python3
"""
Neo4j loader for Cameo requirement connectivity JSON.

This script reads requirements JSON with the following shape:
{
  "nodes": {
    "<req_id>": {
      "name": "<requirement name>",
      "node_type": "Requirement_<type>",
      "text": "<requirement text>",
      "xmi_id": "<xmi_id>",
      "incoming": ["<req_id>", ...],  # Requirements that derive from this one
      "outgoing": ["<req_id>", ...],  # Requirements that this one traces to
      "properties": {...}
    },
    ...
  }
}

Loads into Neo4j with:
- Nodes labeled :Requirement with properties:
  - req_id (string, primary key)
  - name (string)
  - node_type (string, e.g. "Requirement_Functional")
  - text (string) - requirement description/specification
  - xmi_id (string) - original Cameo/MagicDraw ID
  - source_file (string) - originating .mdzip file
  - properties (json) - additional metadata

- Relationships:
  - :DERIVES_FROM - reverse hierarchy/derivation links
  - :REFINES - refinement links
  - :SATISFIES - implementation/satisfaction links
  - :VERIFIES - verification/test links
  - :TRACES_TO - general traceability links

CLI usage:
  python backend/cameo_neo4j_loader.py --json path/to/requirements.json [--wipe-first]
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
from neo4j import GraphDatabase, Driver, Session
from neo4j import GraphDatabase
import json
import os

DEFAULT_URI = os.getenv("NEO4J_URI", "neo4j+s://fa69a4aa.databases.neo4j.io:7687")
DEFAULT_USER = os.getenv("NEO4J_USERNAME", "neo4j")
DEFAULT_PASSWORD = os.getenv("NEO4J_PASSWORD", "nHQVCBIQ0fX4ysrTqHJFyfwWhKvsQfwHdxZGS4g7TUM")
DEFAULT_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

@dataclass
class RequirementNode:
    """Represents a requirement node with its properties and relationships."""
    req_id: str
    name: str
    node_type: str
    text: str
    xmi_id: str
    incoming: List[str]  
    outgoing: List[str]  
    source_file: Optional[str]
    properties: Dict[str, Any]


def validate_requirement_data(data: dict) -> List[str]:
    """Validate requirement data before loading.
    
    Returns a list of validation errors, empty if valid.
    """
    errors = []
    
    if not isinstance(data, dict):
        errors.append("Data must be a dictionary")
        return errors
        
    nodes = data.get("nodes")
    if not isinstance(nodes, dict):
        errors.append("Data must have a 'nodes' dictionary")
        return errors
        
    for req_id, payload in nodes.items():
        if not isinstance(payload, dict):
            errors.append(f"Requirement {req_id}: payload must be a dictionary")
            continue
            
        # Required fields
        if not payload.get("name"):
            errors.append(f"Requirement {req_id}: missing name")
            
        if not payload.get("node_type"):
            errors.append(f"Requirement {req_id}: missing node_type")
            
        # Relationship arrays
        if not isinstance(payload.get("incoming", []), list):
            errors.append(f"Requirement {req_id}: incoming must be a list")
            
        if not isinstance(payload.get("outgoing", []), list):
            errors.append(f"Requirement {req_id}: outgoing must be a list")
            
    return errors


def _parse_nodes_from_data(data: dict) -> Dict[str, RequirementNode]:
    """Parse the JSON data into RequirementNode objects."""
    nodes: Dict[str, RequirementNode] = {}
    
    # Validate data first
    errors = validate_requirement_data(data)
    if errors:
        error_msg = "\n- ".join(["Validation errors:"] + errors)
        raise ValueError(error_msg)
    
    for req_id, payload in data.get("nodes", {}).items():
        node_type = str(payload.get("node_type", ""))
        if node_type.startswith("Requirement_"):
            node_type = node_type[12:] 
        
        # Create structured node object
        nodes[req_id] = RequirementNode(
            req_id=str(req_id),
            name=str(payload.get("name", "")),
            node_type=node_type,
            text=str(payload.get("text", "")),
            xmi_id=str(payload.get("xmi_id", "")),
            incoming=[str(x) for x in payload.get("incoming", [])],
            outgoing=[str(x) for x in payload.get("outgoing", [])],
            source_file=payload.get("source_file"),
            properties=payload.get("properties", {})
        )
    
    return nodes


def get_driver(uri: str, user: str, password: str) -> Driver:
    """Get Neo4j driver with retry logic and validation."""
    try:
        protocols = [
            "neo4j+s://fa69a4aa.databases.neo4j.io:7687",
            "bolt://fa69a4aa.databases.neo4j.io:7687",
            "neo4j://fa69a4aa.databases.neo4j.io:7687"
        ]
        
        last_error = None
        for protocol_uri in protocols:
            try:
                print(f"Attempting connection with: {protocol_uri}")
                driver = GraphDatabase.driver(protocol_uri, auth=(user, password))
                with driver.session(database=DEFAULT_DATABASE) as session:
                    session.run("RETURN 1").single()
                print(f"Successfully connected using: {protocol_uri}")
                return driver
            except Exception as e:
                last_error = e
                print(f"Failed to connect using {protocol_uri}: {e}")
                continue
        
        raise last_error if last_error else Exception("Failed to connect to Neo4j")
        
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}", file=sys.stderr)
        raise


def wipe_graph(session):
    """Remove DERIVES_FROM relationships.  Preserves nodes, manual connections, and versions."""
    print("Clearing DERIVES_FROM relationships...")
    session.run("MATCH ()-[r:DERIVES_FROM]->() DELETE r")


def upsert_requirements(session, reqs: Dict[str, RequirementNode]) -> int:
    """Create or update requirement nodes.
    
    Returns the number of nodes affected.
    """
    if not reqs:
        return 0
        
    query = (
        "UNWIND $rows AS row "
        "MERGE (r:Requirement {req_id: row.req_id}) "
        "SET r.name = row.name, "
        "    r.node_type = row.node_type, "
        "    r.text = row.text, "
        "    r.xmi_id = row.xmi_id, "
        "    r.source_file = row.source_file, "
        "    r.properties = row.properties"
    )
    
    # Convert requirement objects to Neo4j-compatible rows
    rows = [
        {
            "req_id": r.req_id,
            "name": r.name,
            "node_type": r.node_type,
            "text": r.text,
            "xmi_id": r.xmi_id,
            "source_file": r.source_file,
            "properties": json.dumps(r.properties)
        }
        for r in reqs.values()
    ]
    
    result = session.run(query, rows=rows)
    summary = result.consume()
    return summary.counters.nodes_created


def upsert_relationships(session, reqs: Dict[str, RequirementNode]) -> int:
    """Create or update requirement relationships.
    
    Returns the total number of relationships created/updated.
    """
    if not reqs:
        return 0
        
    # Process each relationship type in a single batch for better performance
    rels_to_create = {
        "DERIVES_FROM": [],  # Incoming - child to parent
        "TRACES_TO": []      # Outgoing - all other relationships
    }
    
    # Collect all relationships
    for req_id, req in reqs.items():
        # Derive relationships (parent <- child)
        for parent_id in req.incoming:
            rels_to_create["DERIVES_FROM"].append((req_id, parent_id))
        
        # All other outgoing relationships
        for target_id in req.outgoing:
            rels_to_create["TRACES_TO"].append((req_id, target_id))
    
    total_rels = 0
    for rel_type, pairs in rels_to_create.items():
        if not pairs:
            continue
            
        query = (
            f"UNWIND $pairs AS pair "
            f"MATCH (src:Requirement {{req_id: pair[0]}}), "
            f"      (dst:Requirement {{req_id: pair[1]}}) "
            f"MERGE (src)-[:{rel_type}]->(dst)"
        )
        
        result = session.run(query, pairs=pairs)
        summary = result.consume()
        total_rels += summary.counters.relationships_created
    
    return total_rels


def load_connectivity_json(json_data: dict) -> int:
    """Load requirement data into Neo4j.
    
    Parameters
    ----------
    json_data : dict
        The JSON data containing requirements nodes and relationships.
        
    Returns
    -------
    int
        The number of requirement nodes created/updated.
    """
    try:
        # Parse nodes into structured objects
        reqs = _parse_nodes_from_data(json_data)
        if not reqs:
            print("Warning: No valid requirements found in data", file=sys.stderr)
            return 0
        
        # Connect and load data
        driver = get_driver(DEFAULT_URI, DEFAULT_USER, DEFAULT_PASSWORD)
        try:
            with driver.session(database=DEFAULT_DATABASE) as session:
                # Create/update nodes
                node_count = upsert_requirements(session, reqs)
                
                # Create/update relationships
                rel_count = upsert_relationships(session, reqs)
                
                print(f"Successfully loaded:")
                print(f"  - {node_count} requirement nodes")
                print(f"  - {rel_count} relationships")
                
                return node_count
                
        finally:
            driver.close()
            
    except Exception as e:
        print(f"Error loading requirements: {e}", file=sys.stderr)
        raise

def main():
    """CLI entry point with improved error handling."""
    import argparse
    
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", 
        required=True,
        type=Path,
        help="Path to requirements JSON file"
    )
    parser.add_argument(
        "--wipe-first",
        action="store_true",
        help="Clear DB before import"
    )
    parser.add_argument(
        "--uri",
        default=DEFAULT_URI,
        help="Neo4j URI (default: use environment variable NEO4J_URI)"
    )
    parser.add_argument(
        "--user",
        default=DEFAULT_USER,
        help="Neo4j username (default: use environment variable NEO4J_USER)"
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help="Neo4j password (default: use environment variable NEO4J_PASSWORD)"
    )
    
    args = parser.parse_args()
    
    if not args.json.exists():
        print(f"Error: JSON file not found: {args.json}", file=sys.stderr)
        sys.exit(1)
        
    try:
        # Read JSON file
        print(f"Reading {args.json}...")
        with open(args.json, 'r') as f:
            json_data = json.load(f)
            
        # Parse nodes
        reqs = _parse_nodes_from_data(json_data)
        if not reqs:
            print("Error: No requirements found in JSON", file=sys.stderr)
            sys.exit(1)
            
        print(f"Found {len(reqs)} requirements")
        
        # Connect to Neo4j
        print(f"Connecting to Neo4j at {args.uri}...")
        driver = get_driver(args.uri, args.user, args.password)
        
        try:
            with driver.session(database=DEFAULT_DATABASE) as session:
                # Optionally wipe existing data
                if args.wipe_first:
                    wipe_graph(session)
                    
                # Load nodes
                print(f"Creating/updating requirement nodes...")
                node_count = upsert_requirements(session, reqs)
                
                # Load relationships
                print(f"Creating/updating relationships...")
                rel_count = upsert_relationships(session, reqs)
                
                print("\nImport complete!")
                print(f"Successfully processed:")
                print(f"  - {node_count} requirement nodes")
                print(f"  - {rel_count} relationships")
                
        finally:
            driver.close()
            
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file: {e}", file=sys.stderr)
        sys.exit(1)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


from neo4j import GraphDatabase
import json
import os

def load_requirements_from_cameo(
    json_path="cameo_integration/all_requirements_with_hierarchy.json",  
    uri="neo4j+s://fa69a4aa.databases.neo4j.io",
    user="neo4j",
    password="nHQVCBIQ0fX4ysrTqHJFyfwWhKvsQfwHdxZGS4g7TUM"
):
    if not os.path.exists(json_path):
        print(f"[CAMEO] File not found: {json_path}")
        return

    driver = GraphDatabase.driver(uri, auth=(user, password))

    def create_requirement(tx, req_id, name, node_type, text):
        tx.run("""
            MERGE (r:Requirement {req_id: $req_id})
            SET r.name = $name,
                r.node_type = $node_type,
                r.text = $text
        """, req_id=req_id, name=name, node_type=node_type, text=text)

    def create_derives_from(tx, child_id, parent_id):
        tx.run("""
            MATCH (c:Requirement {req_id: $child_id})
            MATCH (p:Requirement {req_id: $parent_id})
            MERGE (c)-[:DERIVES_FROM]->(p)
        """, child_id=child_id, parent_id=parent_id)

    try:
        with driver.session() as session:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            nodes = data.get("nodes", {})
            total = len(nodes)
            print(f"[CAMEO] Found {total} requirements to load...")

            for i, (req_id, info) in enumerate(nodes.items(), 1):
                name = info.get("name", "Unnamed")
                node_type = info.get("type") or info.get("node_type", "Requirement")
                text = info.get("text", "") or info.get("description", "")

                session.execute_write(create_requirement, req_id, name, node_type, text)

                # Handle hierarchy (incoming = derives FROM parent)
                for parent in info.get("incoming", []):
                    parent_id = parent["id"] if isinstance(parent, dict) else parent
                    if parent_id and parent_id != req_id:
                        session.execute_write(create_derives_from, req_id, parent_id)

                if i % 100 == 0 or i == total:
                    print(f"[CAMEO] Progress: {i}/{total} requirements loaded")

            print(f"[CAMEO] Successfully loaded {total} requirements!")

    except Exception as e:
        print(f"[CAMEO] Failed to load requirements: {e}")
        raise
    finally:
        driver.close()

if __name__ == "__main__":
    load_requirements_from_cameo()