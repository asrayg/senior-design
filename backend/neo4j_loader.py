#!/usr/bin/env python3
"""
Neo4j loader for Simulink block connectivity JSON.

This script reads `block_connectivity.json` with the following shape:

{
  "nodes": {
    "<sid>": {
      "name": "<block name>",
      "node_type": "<block type>",
      "incoming": ["<sid>", ...],
      "outgoing": ["<sid>", ...]
    },
    ...
  }
}

It writes to Neo4j using idempotent MERGE operations:
- Nodes labeled :Block with properties: sid (string), name, node_type
- Relationships :CONNECTS_TO from source -> dest for each outgoing edge

CLI usage:
  python backend/neo4j_loader.py --json backend/block_connectivity.json

Configuration via environment variables (preferred) or CLI flags:
  NEO4J_URI        (e.g. bolt://localhost:7687)
  NEO4J_USER       (e.g. neo4j)
  NEO4J_PASSWORD   (password)

Optional flags:
  --wipe-first     Deletes existing :Block nodes and :CONNECTS_TO rels before import

Examples:
  NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=pass \
    python backend/neo4j_loader.py --json backend/block_connectivity.json --wipe-first
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple

from neo4j import GraphDatabase, Driver


@dataclass
class BlockNode:
    sid: str
    name: str
    node_type: str
    model_name: str
    outgoing: List[str]


def _parse_nodes_from_data(data: dict) -> Dict[str, BlockNode]:
    nodes: Dict[str, BlockNode] = {}
    for sid, payload in data.get("nodes", {}).items():
        nodes[str(sid)] = BlockNode(
            sid=str(sid),
            name=str(payload.get("name", "")),
            node_type=str(payload.get("node_type", "")),
            model_name=str(payload.get("model_name", "")),
            outgoing=[str(x) for x in payload.get("outgoing", [])],
        )
    return nodes


def read_block_connectivity(json_path: str) -> Dict[str, BlockNode]:
    with open(json_path, "r") as f:
        data = json.load(f)
    return _parse_nodes_from_data(data)


def get_driver(uri: str, user: str, password: str) -> Driver:
    return GraphDatabase.driver(uri, auth=(user, password))


# Default connection settings (fixed; not read from environment)
DEFAULT_URI = "neo4j+s://fa69a4aa.databases.neo4j.io"
DEFAULT_USER = "neo4j"
DEFAULT_PASSWORD = "nHQVCBIQ0fX4ysrTqHJFyfwWhKvsQfwHdxZGS4g7TUM"
DEFAULT_DATABASE = "neo4j"


def wipe_graph(session):
    session.run("MATCH (n:Block) DETACH DELETE n")


def upsert_blocks(session, blocks: Dict[str, BlockNode]):
    query = (
        "UNWIND $rows AS row "
        "MERGE (b:Block {sid: row.sid}) "
        "SET b.name = row.name, b.node_type = row.node_type, b.model_name = row.model_name"
    )
    rows = [
        {"sid": b.sid, "name": b.name, "node_type": b.node_type, "model_name": b.model_name}
        for b in blocks.values()
    ]
    session.run(query, rows=rows)


def upsert_relationships(session, blocks: Dict[str, BlockNode]):
    rel_rows: List[Tuple[str, str]] = []
    for src_sid, block in blocks.items():
        for dst_sid in block.outgoing:
            rel_rows.append((src_sid, dst_sid))

    if not rel_rows:
        return

    query = (
        "UNWIND $pairs AS pair "
        "MATCH (src:Block {sid: pair[0]}), (dst:Block {sid: pair[1]}) "
        "MERGE (src)-[:CONNECTS_TO]->(dst)"
    )
    session.run(query, pairs=rel_rows)


def load_connectivity_json(json_data: dict, filename: str = None) -> Tuple[int, str]:
    """Library entry point: import a JSON object into Neo4j.

    Parameters are optional; when omitted, environment variables are used with
    sensible defaults for local development.
    
    Args:
        json_data: The JSON data to load
        filename: The filename (used for logging, stored as model_name on blocks)
    
    Returns:
        Tuple[int, str]: Number of nodes loaded and the filename
    """

    nodes = _parse_nodes_from_data(json_data)
    if not nodes:
        return (0, "")

    if filename is None:
        filename = ""

    driver = get_driver(DEFAULT_URI, DEFAULT_USER, DEFAULT_PASSWORD)
    try:
        with driver.session(database=DEFAULT_DATABASE) as session:
            # Load blocks and their relationships (no parent node)
            upsert_blocks(session, nodes)
            upsert_relationships(session, nodes)
    finally:
        driver.close()

    return (len(nodes), filename)
