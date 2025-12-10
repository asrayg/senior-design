import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from neo4j import GraphDatabase

class ConnectionVersion:
    def __init__(self, model_id: str, connections_hash: str, timestamp: str, connection_count: int):
        self.model_id = model_id
        self.connections_hash = connections_hash
        self.timestamp = timestamp
        self.connection_count = connection_count
    
    def to_dict(self):
        return {
            "model_id": self.model_id,
            "connections_hash": self.connections_hash,
            "timestamp": self.timestamp,
            "connection_count": self.connection_count
        }


def compute_connections_hash(connections: List[Tuple[str, str]]) -> str:
    sorted_conns = sorted(connections)
    connections_str = json.dumps(sorted_conns, sort_keys=True)
    return hashlib.sha256(connections_str.encode()).hexdigest()


def extract_connections_from_json(json_data: dict) -> List[Tuple[str, str]]:
    connections = []
    nodes = json_data.get("nodes", {})
    
    for src_sid, node_data in nodes.items():
        outgoing = node_data.get("outgoing", [])
        for dst_sid in outgoing:
            connections.append((str(src_sid), str(dst_sid)))
    
    return connections


class ConnectionVersioningLoader:
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def track_model_connections(self, model_name: str, json_data: dict, batch_size: int = 100):
        """
        Track model connections with batching for performance.
        
        Args:
            model_name: Name of the model
            json_data: Connection data in JSON format
            batch_size: Number of connections to process in one query (default: 100)
        """
        connections = extract_connections_from_json(json_data)
        conn_hash = compute_connections_hash(connections)
        timestamp = datetime.utcnow().isoformat()
        
        with self.driver.session() as session:
            query = """
            MERGE (mv:ModelVersion {model_id: $model_id})
            SET mv.timestamp = $timestamp,
                mv.connections_hash = $conn_hash,
                mv.connection_count = $conn_count
            RETURN mv
            """
            session.run(
                query,
                model_id=model_name,
                timestamp=timestamp,
                conn_hash=conn_hash,
                conn_count=len(connections)
            )
            query = """
            CREATE (cv:ConnectionVersion {
                version_id: $version_id,
                model_id: $model_id,
                timestamp: $timestamp,
                connection_count: $conn_count,
                connections_hash: $conn_hash
            })
            """
            session.run(
                query,
                version_id=conn_hash,
                model_id=model_name,
                timestamp=timestamp,
                conn_count=len(connections),
                conn_hash=conn_hash
            )
            
            # Batch process connections - process multiple in one query
            for i in range(0, len(connections), batch_size):
                batch = connections[i:i + batch_size]
                
                # Convert batch to parameter format for bulk processing
                batch_params = [
                    {"src_sid": src_sid, "dst_sid": dst_sid}
                    for src_sid, dst_sid in batch
                ]
                
                query = """
                UNWIND $connections as conn
                MATCH (src:Block {sid: conn.src_sid}), (dst:Block {sid: conn.dst_sid})
                MERGE (src)-[rel:CONNECTS_TO]->(dst)
                ON CREATE SET rel.created_at = $timestamp,
                              rel.version_id = $version_id,
                              rel.last_seen = $timestamp
                ON MATCH SET rel.last_seen = $timestamp,
                             rel.version_id = $version_id
                """
                try:
                    session.run(
                        query,
                        connections=batch_params,
                        timestamp=timestamp,
                        version_id=conn_hash
                    )
                except Exception as e:
                    print(f"Warning: Error processing batch {i//batch_size + 1}: {e}")
    
    def get_connection_history(self, model_name: str) -> List[dict]:
        with self.driver.session() as session:
            query = """
            MATCH (cv:ConnectionVersion {model_id: $model_id})
            RETURN cv.version_id as version_id,
                   cv.timestamp as timestamp,
                   cv.connection_count as count,
                   cv.connections_hash as hash
            ORDER BY cv.timestamp DESC
            """
            result = session.run(query, model_id=model_name)
            return [dict(record) for record in result]
    
    def get_current_connections(self, model_name: str) -> List[Tuple[str, str]]:
        with self.driver.session() as session:
            query = """
            MATCH (src:Block)-[:CONNECTS_TO]->(dst:Block)
            WHERE src.model = $model_name OR dst.model = $model_name
            RETURN src.sid as src, dst.sid as dst
            """
            result = session.run(query, model_name=model_name)
            return [(record['src'], record['dst']) for record in result]
