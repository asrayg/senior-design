#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import hashlib
from neo4j import GraphDatabase

from neo4j import GraphDatabase, Driver
from versioning.schema import ArtifactVersion
from enums import Tool, ArtifactType


class VersioningLoader:
    """Loads artifact versions into Neo4j."""
    
    def __init__(self, uri: str, user: str, password: str):
        """Initialize the versioning loader with Neo4j credentials."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.uri = uri
        self.user = user
        self.password = password
    
    def close(self):
        """Close the database connection."""
        self.driver.close()
    
    def clear_versions(self):
        """Clear all version nodes and relationships from database."""
        with self.driver.session(database="neo4j") as session:
            session.run("MATCH (v:ArtifactVersion) DETACH DELETE v")
            session.run("MATCH ()-[r:HAS_VERSION]->() DELETE r")
            session.run("MATCH ()-[r:VERSION_OF]->() DELETE r")
        print("✓ Cleared all version data")
    
    def load_artifact_versions(self, versions: Dict[str, ArtifactVersion], tool: Tool):
        """
        Load a collection of artifact versions into the database.
        
        Args:
            versions: Dictionary of {artifact_id: ArtifactVersion}
            tool: Tool enum (Tool.SIMULINK or Tool.CAMEO)
        """
        if not versions:
            print(f"  No versions to load for {tool.value}")
            return
        
        print(f"  Loading {len(versions)} {tool.value} artifact versions...")
        
        with self.driver.session(database="neo4j") as session:
            for artifact_id, version in versions.items():
                self._create_version_node(
                    session, 
                    artifact_id, 
                    version, 
                    tool
                )
        
        print(f"  ✓ Loaded {len(versions)} {tool.value} versions")
    
    def _create_version_node(
        self, 
        session, 
        artifact_id: str, 
        version: ArtifactVersion,
        tool: Tool
    ):
        """Create a version node and link it to the artifact."""
        
        existing = session.run("""
            MATCH (v:ArtifactVersion {artifact_id: $artifact_id})
            WHERE v.snapshot = $snapshot OR v.version_id = $version_id
            RETURN count(v) as count
        """, artifact_id=artifact_id, snapshot=version.snapshot, version_id=version.version_id). single()['count']
        
        if existing > 0:
            return
    
        # Determine artifact label and ID field based on tool
        if tool == Tool.SIMULINK:
            artifact_label = "Block"
            id_field = "sid"
        else:  # Tool.CAMEO
            artifact_label = "Requirement"
            id_field = "req_id"
        
        query = f"""
        MERGE (artifact:{artifact_label} {{
            {id_field}: $artifact_id
        }})
        MERGE (version:ArtifactVersion {{
            version_id: $version_id,
            artifact_id: $artifact_id
        }})
        SET version.artifact_type = $artifact_type,
            version.tool = $tool,
            version.timestamp = $timestamp,
            version.parent_version_id = $parent_version_id
        MERGE (artifact)-[:HAS_VERSION]->(version)
        """
        
        session.run(
            query,
            artifact_id=artifact_id,
            version_id=version.version_id,
            artifact_type=version.artifact_type,
            tool=tool.value,
            timestamp=version.timestamp,
            parent_version_id=version.parent_version_id
        )
    
    def create_version_lineage(self):
        """Create relationships between versions showing their lineage."""
        with self.driver.session(database="neo4j") as session:
            query = """
            MATCH (v1:ArtifactVersion)-[:HAS_VERSION]->(a:Artifact)
            MATCH (v2:ArtifactVersion {parent_version_id: v1.version_id})
            MERGE (v2)-[:DERIVED_FROM]->(v1)
            """
            session.run(query)
        
        print("  ✓ Created version lineage relationships")
    
    def get_version_stats(self) -> Dict:
        """Get statistics about loaded versions."""
        with self.driver.session(database="neo4j") as session:
            stats = {}
            
            result = session.run("MATCH (v:ArtifactVersion) RETURN count(v) as count")
            stats['total_versions'] = result.single()['count']
            
            result = session.run("""
                MATCH (v:ArtifactVersion)
                RETURN v.tool as tool, count(v) as count
                ORDER BY tool
            """)
            stats['by_tool'] = {r['tool']: r['count'] for r in result}
            
            result = session.run("""
                MATCH (v:ArtifactVersion)
                RETURN v.artifact_type as type, count(v) as count
                ORDER BY type
            """)
            stats['by_type'] = {r['type']: r['count'] for r in result}
            
            return stats


def load_simulink_versions_to_neo4j(loader: VersioningLoader):
    """Load Simulink block versions from versioning tracker."""
    print("\n" + "="*70)
    print("LOADING SIMULINK BLOCK VERSIONS TO NEO4J")
    print("="*70)
    
    sys.path.insert(0, str(Path(__file__).parent))
    from versioning.simulink_tracker import track_simulink_blocks
    
    versions, new_count, changed_count = track_simulink_blocks()
    
    if versions:
        loader.load_artifact_versions(versions, Tool.SIMULINK)
        print(f"  Summary: {new_count} new, {changed_count} changed")
    
    return versions


def load_cameo_versions_to_neo4j(loader: VersioningLoader):
    """Load CAMEO requirement versions from versioning tracker."""
    print("\n" + "="*70)
    print("LOADING CAMEO REQUIREMENT VERSIONS TO NEO4J")
    print("="*70)
    sys.path.insert(0, str(Path(__file__).parent))
    from versioning.cameo_tracker import track_cameo_requirements
    
    versions, new_count, changed_count = track_cameo_requirements()
    
    if versions:
        loader.load_artifact_versions(versions, Tool.CAMEO)
        print(f"  Summary: {new_count} new, {changed_count} changed")
    
    return versions


def load_all_versions_to_neo4j(
    uri: str, 
    user: str, 
    password: str,
    clear_first: bool = False
):
    """Load all artifact versions into Neo4j."""
    loader = VersioningLoader(uri, user, password)
    
    try:
        if clear_first:
            loader.clear_versions()
        
        simulink_versions = load_simulink_versions_to_neo4j(loader)
        
        cameo_versions = load_cameo_versions_to_neo4j(loader)
        
        if simulink_versions or cameo_versions:
            loader.create_version_lineage()
        
        stats = loader.get_version_stats()
        print("\n" + "="*70)
        print("VERSION LOADING COMPLETE")
        print("="*70)
        print(f"Total versions loaded: {stats['total_versions']}")
        if 'by_tool' in stats:
            for tool, count in stats['by_tool'].items():
                print(f"  {tool}: {count}")
        
        return stats
    
    finally:
        loader.close()
        
def create_initial_snapshot(uri: str, user: str, password: str):
    """Create initial version snapshot for all existing artifacts - ONLY if no versions exist."""
    from neo4j import GraphDatabase
    
    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        marker = session.run(
            "MATCH (m:VersioningMarker {id: 'initialized'}) RETURN m"
        ).single()
        
        if marker:
            print("Versioning already initialized - skipping initial snapshot creation")
            driver.close()
            return
        
        existing = session.run(
            "MATCH (v:ArtifactVersion) RETURN count(v) as count"
        ).single()['count']
        
        if existing > 0:
            print(f"Found {existing} existing versions - skipping initial snapshot creation")
            driver.close()
            return

    timestamp = datetime.utcnow().isoformat()
    
    with driver.session() as session:
        blocks = session.run("""
            MATCH (b:Block)
            WHERE NOT (b)-[:HAS_VERSION]->(:ArtifactVersion)
            OPTIONAL MATCH (b)-[:CONNECTS_TO]->(target:Block)
            OPTIONAL MATCH (source:Block)-[:CONNECTS_TO]->(b)
            OPTIONAL MATCH (b)-[:SATISFIES]->(req:Requirement)
            RETURN b.sid as sid, 
                   b. name as name, 
                   b.node_type as type,
                   collect(DISTINCT target.sid) as outgoing,
                   collect(DISTINCT source.sid) as incoming,
                   collect(DISTINCT req.req_id) as satisfies
        """)
        
        block_count = 0
        for block in blocks:
            graph_snapshot = {
                "sid": block['sid'],
                "name": block['name'],
                "type": block['type'],
                "connections": {
                    "outgoing": sorted([s for s in block['outgoing'] if s]),
                    "incoming": sorted([s for s in block['incoming'] if s]),
                    "satisfies": sorted([s for s in block['satisfies'] if s])
                }
            }
            
            snapshot_str = json.dumps(graph_snapshot, sort_keys=True)
            version_hash = hashlib.sha256(snapshot_str.encode()). hexdigest()[:16]
            version_id = f"{block['sid']}_v1_{version_hash}"
            
            session.run("""
                MERGE (v:ArtifactVersion {version_id: $version_id})
                ON CREATE SET v.artifact_id = $sid,
                            v.artifact_type = 'block',
                            v.tool = 'simulink',
                            v.timestamp = $timestamp,
                            v. version_number = 1,
                            v.snapshot = $snapshot,
                            v.is_initial = true
            """, sid=block['sid'], version_id=version_id, 
                timestamp=timestamp, snapshot=snapshot_str)

            session.run("""
                MATCH (b:Block {sid: $sid})
                MATCH (v:ArtifactVersion {version_id: $version_id})
                MERGE (b)-[:HAS_VERSION]->(v)
            """, sid=block['sid'], version_id=version_id)
            block_count += 1
        
        requirements = session.run("""
            MATCH (r:Requirement)
            WHERE NOT (r)-[:HAS_VERSION]->(:ArtifactVersion)
            OPTIONAL MATCH (r)-[:DERIVES_FROM]->(parent:Requirement)
            OPTIONAL MATCH (child:Requirement)-[:DERIVES_FROM]->(r)
            OPTIONAL MATCH (r)-[:SATISFIES]-(block)
            OPTIONAL MATCH (r)-[:TRACES_TO]->(traced:Requirement)
            OPTIONAL MATCH (tracer:Requirement)-[:TRACES_TO]->(r)
            RETURN r. req_id as req_id, 
                r.name as name, 
                r.node_type as type,
                collect(DISTINCT parent.req_id) as parents,
                collect(DISTINCT child.req_id) as children,
                collect(DISTINCT coalesce(block.sid, block.id)) as linked_blocks,
                collect(DISTINCT traced.req_id) as traces_to,
                collect(DISTINCT tracer.req_id) as traced_by
        """)

        req_count = 0
        for req in requirements:
            graph_snapshot = {
                "req_id": req['req_id'],
                "name": req['name'],
                "type": req['type'],
                "relationships": {
                    "derives_from": sorted([p for p in req['parents'] if p]),
                    "derived_by": sorted([c for c in req['children'] if c]),
                    "satisfies": sorted([b for b in req['linked_blocks'] if b]),
                    "traces_to": sorted([t for t in req['traces_to'] if t]),
                    "traced_by": sorted([t for t in req['traced_by'] if t])
                }
            }
            
            session.run("""
                MERGE (v:ArtifactVersion {version_id: $version_id})
                ON CREATE SET v.artifact_id = $req_id,
                            v.artifact_type = 'requirement',
                            v.tool = 'cameo',
                            v. timestamp = $timestamp,
                            v.version_number = 1,
                            v.snapshot = $snapshot,
                            v. is_initial = true
            """, req_id=req['req_id'], version_id=version_id,
                timestamp=timestamp, snapshot=snapshot_str)

            session.run("""
                MATCH (r:Requirement {req_id: $req_id})
                MATCH (v:ArtifactVersion {version_id: $version_id})
                MERGE (r)-[:HAS_VERSION]->(v)
            """, req_id=req['req_id'], version_id=version_id)
            req_count += 1
        
        if block_count > 0 or req_count > 0:
            print(f"Created initial snapshots: {block_count} blocks, {req_count} requirements")
    
    driver.close()

if __name__ == "__main__":
    from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    
    load_all_versions_to_neo4j(
        NEO4J_URI,
        NEO4J_USER,
        NEO4J_PASSWORD,
        clear_first=True
    )