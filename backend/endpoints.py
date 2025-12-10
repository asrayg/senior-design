from typing import Any, Dict, List
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from neo4j import GraphDatabase
import json
import os
from glob import glob
from config import LOCAL_REPO_PATH
from simulink_analyzer import SlxcAnalyzer

app = Flask(__name__)
CORS(app)

uri = "neo4j+s://fa69a4aa.databases.neo4j.io"
user = "neo4j"
password = "nHQVCBIQ0fX4ysrTqHJFyfwWhKvsQfwHdxZGS4g7TUM"
driver = GraphDatabase.driver(uri, auth=(user, password))


def load_code_mappings() -> Dict[str, List[Dict]]:
    """Load all code mappings from *_code_mappings.json files.
    
    Returns a dict mapping block_name -> list of code references.
    """
    mappings_by_name: Dict[str, List[Dict]] = {}
    
    # Find all code_mappings.json files in the repo path
    pattern = os.path.join(LOCAL_REPO_PATH, "*_code_mappings.json")
    for mapping_file in glob(pattern):
        try:
            with open(mapping_file, 'r') as f:
                data = json.load(f)
            
            for mapping in data.get("mappings", []):
                block_name = mapping.get("block_name")
                if block_name:
                    if block_name not in mappings_by_name:
                        mappings_by_name[block_name] = []
                    mappings_by_name[block_name].append({
                        "location": mapping.get("location"),
                        "file_path": mapping.get("file_path"),
                        "block_path": mapping.get("block_path"),
                        "code_references": mapping.get("code_references", [])
                    })
        except Exception as e:
            print(f"Error loading code mappings from {mapping_file}: {e}")
    
    return mappings_by_name


def get_slxc_c_files(model_name: str) -> Dict[str, str]:
    """Load C files from a .slxc archive for a given model name.
    
    First checks for pre-extracted directory for fast access.
    
    Args:
        model_name: Name of the model (e.g., 'MultiRateComponent')
    
    Returns:
        Dict mapping file paths to their content
    """
    # Look for .slxc file in the repo path
    slxc_path = os.path.join(LOCAL_REPO_PATH, f"{model_name}.slxc")
    
    if not os.path.exists(slxc_path):
        # Try without extension in case user passed full filename
        if model_name.endswith('.slxc'):
            slxc_path = os.path.join(LOCAL_REPO_PATH, model_name)
        else:
            return {}
    
    if not os.path.exists(slxc_path):
        return {}
    
    # Check for pre-extracted directory first (faster)
    extracted_dir = SlxcAnalyzer.get_extracted_dir(slxc_path)
    if extracted_dir.exists():
        return SlxcAnalyzer.load_from_extracted(str(extracted_dir))
    
    # Fall back to extracting (will keep extracted for next time)
    analyzer = SlxcAnalyzer(slxc_path)
    if not analyzer.load_slxc(keep_extracted=True):
        return {}
    
    return dict(analyzer.c_files)


def build_requirement_tree(session, root_id, visited=None, all_nodes=None):
    if visited is None:
        visited = set()
    if all_nodes is None:
        all_nodes = {}

    if root_id in visited:
        return {"id": root_id, "name": "(cycle)", "children": [], "incoming": [], "outgoing": []}

    visited.add(root_id)

    record = session.run(
        """
        MATCH (r:Requirement {req_id: $id})
        RETURN r.req_id AS id, r.name AS name,
               r.node_type AS type, r.text AS description
        """,
        id=root_id
    ).single()

    if not record:
        return None

    node = {
        "id": record["id"],
        "name": record["name"],
        "type": record.get("type"),
        "description": record.get("description"),
        "children": [],
        "incoming": [],
        "outgoing": []
    }
    all_nodes[root_id] = node

    children = session.run(
        """
        MATCH (parent:Requirement {req_id: $id})<-[:DERIVES_FROM]-(child:Requirement)
        RETURN child.req_id AS id, child.name AS name
        """,
        id=root_id
    )

    for child in children:
        child_tree = build_requirement_tree(session, child["id"], visited.copy(), all_nodes)
        if child_tree:
            node["children"].append(child_tree)
            child_tree["incoming"].append({"id": root_id, "name": record["name"]})
            node["outgoing"].append({"id": child["id"], "name": child["name"]})

    parents = session.run(
        """
        MATCH (child:Requirement {req_id: $id})-[:DERIVES_FROM]->(parent:Requirement)
        RETURN parent.req_id AS id, parent.name AS name
        """,
        id=root_id
    )
    for parent in parents:
        node["incoming"].append({"id": parent["id"], "name": parent["name"]})

    # Get outgoing TRACES_TO relationships
    traces_out = session.run(
        """
        MATCH (r:Requirement {req_id: $id})-[:TRACES_TO]->(related:Requirement)
        RETURN related. req_id AS id, related. name AS name
        """,
        id=root_id
    )
    for trace in traces_out:
        node["outgoing"].append({"id": trace["id"], "name": trace["name"], "type": "TRACES_TO"})

    # Get incoming TRACES_TO relationships
    traces_in = session.run(
        """
        MATCH (related:Requirement)-[:TRACES_TO]->(r:Requirement {req_id: $id})
        RETURN related.req_id AS id, related.name AS name
        """,
        id=root_id
    )
    for trace in traces_in:
        node["incoming"].append({"id": trace["id"], "name": trace["name"], "type": "TRACES_TO"})

    return node


def build_block_tree(session, root_sid, visited=None, all_nodes=None, code_mappings=None):
    if visited is None:
        visited = set()
    if all_nodes is None:
        all_nodes = {}
    if code_mappings is None:
        code_mappings = {}

    if root_sid in visited:
        return None

    visited.add(root_sid)

    record = session.run(
        """
        MATCH (n:Block {sid: $sid})
        RETURN n.sid AS sid, n.name AS name, n.node_type AS type, n.text AS text, n.edited_code_references AS edited_code_references
        """,
        sid=root_sid
    ).single()

    if not record:
        return None

    block_name = record["name"]
    
    # Get code references for this block if they exist
    generated_code = code_mappings.get(block_name, [])
    
    # Apply edited code references if they exist
    edited_refs_str = record.get("edited_code_references")
    if edited_refs_str:
        try:
            edited_refs = json.loads(edited_refs_str) if isinstance(edited_refs_str, str) else edited_refs_str
            # Merge edited references into generated_code
            for code_mapping in generated_code:
                ref_key = f"{code_mapping.get('file_path', '')}:{code_mapping.get('block_path', '')}"
                if ref_key in edited_refs:
                    edited_refs_list = edited_refs[ref_key]
                    # Apply edits to code_references
                    if code_mapping.get('code_references') and edited_refs_list:
                        for ref_index, edited_ref in enumerate(edited_refs_list):
                            if ref_index < len(code_mapping['code_references']) and edited_ref:
                                # Merge edited values
                                if 'line' in edited_ref:
                                    code_mapping['code_references'][ref_index]['line'] = edited_ref['line']
                                if 'code' in edited_ref:
                                    code_mapping['code_references'][ref_index]['code'] = edited_ref['code']
        except Exception as e:
            print(f"Warning: Could not parse edited_code_references for {block_name}: {e}")
    
    node = {
        "sid": record["sid"],
        "name": block_name,
        "type": record.get("type"),
        "text": record.get("text"),
        "children": [],
        "incoming": [],
        "outgoing": [],
        "generated_code": generated_code
    }
    all_nodes[root_sid] = node

    children = session.run(
        """
        MATCH (n:Block {sid: $sid})-[:CONNECTS_TO]->(m:Block)
        RETURN m.sid AS sid, m.name AS name
        """,
        sid=root_sid
    )

    for child in children:
        child_tree = build_block_tree(session, child["sid"], visited.copy(), all_nodes, code_mappings)
        if child_tree:
            node["children"].append(child_tree)

    return node


# ----------------------------------------------------------------------
# ENDPOINTS
# ----------------------------------------------------------------------
@app.route('/api/requirements', methods=['GET'])
def get_requirements():
    try:
        with driver.session() as session:
            req_type = request.args.get('type')
            search = request.args.get('search')

            query = "MATCH (r:Requirement) WHERE 1=1"
            params = {}

            if req_type:
                query += " AND r.node_type = $type"
                params['type'] = req_type
            if search:
                query += " AND (r.name CONTAINS $search OR r.text CONTAINS $search)"
                params['search'] = search

            query += """
                RETURN r.req_id as id, r.name as name, r.node_type as type, r.text as description
                ORDER BY r.req_id
            """
            result = session.run(query, params)
            return jsonify([dict(r) for r in result])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/requirements/<req_id>', methods=['GET'])
def get_requirement(req_id):
    try:
        with driver.session() as session:
            tree = build_requirement_tree(session, req_id)
            if tree:
                return jsonify(tree)
            return jsonify({"error": "Not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/requirements/hierarchy', methods=['GET'])
def get_requirement_hierarchy():
    try:
        with driver.session() as session:
            # FIXED: Root nodes are those that don't derive FROM anything
            # So we look for nodes with no outgoing DERIVES_FROM relationships
            roots = session.run(
                """
                MATCH (r:Requirement)
                WHERE NOT (r)-[:DERIVES_FROM]->()
                RETURN r.req_id AS id, r.name AS name
                ORDER BY r.req_id
                """
            ).data()

            forest = []
            all_nodes = {}
            for root in roots:
                tree = build_requirement_tree(session, root["id"], all_nodes=all_nodes)
                if tree:
                    forest.append(tree)

            return jsonify(forest)  # Always return a list
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/requirements/stats', methods=['GET'])
def get_requirement_stats():
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (r:Requirement)
                WITH count(r) as total
                MATCH (r:Requirement)
                OPTIONAL MATCH (r)<-[:DERIVES_FROM]-(c)
                OPTIONAL MATCH (r)-[:TRACES_TO]->(t)
                RETURN total,
                       count(DISTINCT r.node_type) as type_count,
                       count(c) as child_count,
                       count(t) as trace_count
            """)
            stats = result.single()
            return jsonify({
                "total": stats["total"],
                "types": stats["type_count"],
                "with_children": stats["child_count"],
                "with_traces": stats["trace_count"]
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/baseline")
def baseline():
    try:
        # Load code mappings from .slxc analysis
        code_mappings = load_code_mappings()
        
        with driver.session(database="neo4j") as session:
            # Fetch ALL blocks in one query (instead of one query per block)
            all_blocks_result = session.run("""
                MATCH (n:Block)
                RETURN n.sid AS sid, n.name AS name, n.node_type AS type, n.text AS text, n.edited_code_references AS edited_code_references
            """)
            all_blocks = {r['sid']: dict(r) for r in all_blocks_result}
            
            # Fetch ALL connections in one query
            all_connections_result = session.run("""
                MATCH (src:Block)-[:CONNECTS_TO]->(dst:Block)
                RETURN src.sid AS src_sid, dst.sid AS dst_sid
            """)
            
            # Build adjacency list in memory
            children_map: Dict[str, List[str]] = {}
            has_parent: set = set()
            
            for conn in all_connections_result:
                src_sid = conn['src_sid']
                dst_sid = conn['dst_sid']
                if src_sid not in children_map:
                    children_map[src_sid] = []
                children_map[src_sid].append(dst_sid)
                has_parent.add(dst_sid)
            
            # Find roots (blocks with no incoming CONNECTS_TO)
            roots = [sid for sid in all_blocks.keys() if sid not in has_parent]
            roots.sort(key=lambda sid: all_blocks[sid].get('name') or '')
            
            # Build trees in memory (no more DB calls)
            def build_tree_fast(sid, visited=None):
                if visited is None:
                    visited = set()
                if sid in visited:
                    return None
                visited.add(sid)
                
                block = all_blocks.get(sid)
                if not block:
                    return None
                
                block_name = block['name']
                generated_code = code_mappings.get(block_name, [])
                
                # Apply edited code references if they exist
                edited_refs_str = block.get("edited_code_references")
                if edited_refs_str:
                    try:
                        edited_refs = json.loads(edited_refs_str) if isinstance(edited_refs_str, str) else edited_refs_str
                        # Merge edited references into generated_code
                        for code_mapping in generated_code:
                            ref_key = f"{code_mapping.get('file_path', '')}:{code_mapping.get('block_path', '')}"
                            if ref_key in edited_refs:
                                edited_refs_list = edited_refs[ref_key]
                                # Apply edits to code_references
                                if code_mapping.get('code_references') and edited_refs_list:
                                    for ref_index, edited_ref in enumerate(edited_refs_list):
                                        if ref_index < len(code_mapping['code_references']) and edited_ref:
                                            # Merge edited values
                                            if 'line' in edited_ref:
                                                code_mapping['code_references'][ref_index]['line'] = edited_ref['line']
                                            if 'code' in edited_ref:
                                                code_mapping['code_references'][ref_index]['code'] = edited_ref['code']
                    except Exception as e:
                        print(f"Warning: Could not parse edited_code_references for {block_name}: {e}")
                
                node = {
                    "sid": block['sid'],
                    "name": block_name,
                    "type": block.get('type'),
                    "text": block.get('text'),
                    "children": [],
                    "incoming": [],
                    "outgoing": [],
                    "generated_code": generated_code
                }
                
                for child_sid in children_map.get(sid, []):
                    child_tree = build_tree_fast(child_sid, visited.copy())
                    if child_tree:
                        node["children"].append(child_tree)
                
                return node
            
            trees = []
            for root_sid in roots:
                tree = build_tree_fast(root_sid)
                if tree:
                    trees.append(tree)

            response = trees[0] if len(trees) == 1 else trees
            return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/code-file', methods=['GET'])
def get_code_file_by_path():
    """Get a C code file by its path (searches all .slxc files).
    
    Uses pre-extracted directories for fast access.
    
    Query params:
        file_path: The file path from the baseline generated_code response
        raw: If 'true', return raw text instead of JSON
    
    Example:
        /api/code-file?file_path=R2025b/glnxa64/.../MultiRateComponent.c
    """
    try:
        file_path = request.args.get('file_path')
        
        if not file_path:
            return jsonify({"error": "file_path query parameter is required"}), 400
        
        # Search all .slxc files for this file
        slxc_files = glob(os.path.join(LOCAL_REPO_PATH, "*.slxc"))
        
        for slxc_path in slxc_files:
            model_name = os.path.splitext(os.path.basename(slxc_path))[0]
            
            # Check for pre-extracted directory first (fast path)
            extracted_dir = SlxcAnalyzer.get_extracted_dir(slxc_path)
            if extracted_dir.exists():
                c_files = SlxcAnalyzer.load_from_extracted(str(extracted_dir))
            else:
                # Fall back to extracting (will keep for next time)
                analyzer = SlxcAnalyzer(slxc_path)
                if not analyzer.load_slxc(keep_extracted=True):
                    continue
                c_files = analyzer.c_files
            
            # Check if this archive has the file
            for path, content in c_files.items():
                if path == file_path or path.endswith(file_path) or file_path.endswith(path):
                    # Return raw if requested
                    if request.args.get('raw') == 'true':
                        return Response(content, mimetype='text/plain')
                    
                    return jsonify({
                        "model_name": model_name,
                        "file_path": path,
                        "content": content,
                        "line_count": len(content.split('\n'))
                    })
        
        return jsonify({
            "error": f"File not found in any .slxc archive",
            "searched_path": file_path,
            "searched_archives": [os.path.basename(f) for f in slxc_files]
        }), 404
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/code-references/update', methods=['POST', 'OPTIONS'])
def update_code_reference():
    """Update a code reference (line number or code text) for a block.
    
    Request body:
        block_sid: The SID of the block
        block_path: The block path (e.g., "<Root>/F1")
        file_path: The file path
        ref_index: Index of the code reference in the array
        line: New line number
        code: New code text
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response
    
    try:
        data = request.get_json()
        block_sid = data.get('block_sid')
        block_path = data.get('block_path')
        file_path = data.get('file_path')
        ref_index = data.get('ref_index')
        line = data.get('line')
        code = data.get('code')
        
        if not all([block_sid, block_path, file_path, ref_index is not None]):
            return jsonify({"error": "Missing required fields"}), 400
        
        with driver.session() as session:
            # Get the current block and its edited_code_references property
            result = session.run("""
                MATCH (b:Block {sid: $sid})
                RETURN b.edited_code_references AS edited_code_references
            """, sid=block_sid).single()
            
            if not result:
                return jsonify({"error": "Block not found"}), 404
            
            # Get or initialize edited_code_references property
            edited_refs_raw = result.get('edited_code_references')
            
            # Parse the value - handle string, dict, or None
            edited_refs = {}
            if edited_refs_raw is not None:
                if isinstance(edited_refs_raw, str):
                    try:
                        edited_refs = json.loads(edited_refs_raw)
                    except (json.JSONDecodeError, TypeError):
                        edited_refs = {}
                elif isinstance(edited_refs_raw, dict):
                    edited_refs = edited_refs_raw
                else:
                    edited_refs = {}
            
            # Create key for this code reference
            ref_key = f"{file_path}:{block_path}"
            if ref_key not in edited_refs:
                edited_refs[ref_key] = []
            
            # Ensure the array is long enough
            while len(edited_refs[ref_key]) <= ref_index:
                edited_refs[ref_key].append({})
            
            # Update the specific reference
            edited_refs[ref_key][ref_index] = {
                "line": line,
                "code": code
            }
            
            # Save back to Neo4j
            session.run("""
                MATCH (b:Block {sid: $sid})
                SET b.edited_code_references = $edited_refs
            """, sid=block_sid, edited_refs=json.dumps(edited_refs))
            
            return jsonify({
                "success": True,
                "message": "Code reference updated",
                "updated_ref": edited_refs[ref_key][ref_index]
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/connect', methods=['POST'])
def create_manual_connection():
    """Create a manual connection between two nodes and record version history."""
    try:
        data = request.get_json()
        source = data.get('source')
        target = data.get('target')
        
        if not source or not target:
            return jsonify({"error": "Source and target required"}), 400
        
        print(f"Connecting: {source} -> {target}")
            
        with driver. session() as session:
            result = None
            relationship_type = None
            
            connection_attempts = [
                ("""
                    MATCH (src:Requirement {req_id: $source})
                    MATCH (tgt:Requirement {req_id: $target})
                    MERGE (src)-[r:TRACES_TO]->(tgt)
                    RETURN src.req_id as src_id, tgt. req_id as tgt_id
                """, "TRACES_TO", "Requirement->Requirement"),
                ("""
                    MATCH (src:Block {sid: $source})
                    MATCH (tgt:Block {sid: $target})
                    MERGE (src)-[r:CONNECTS_TO]->(tgt)
                    RETURN src.sid as src_id, tgt.sid as tgt_id
                """, "CONNECTS_TO", "Block->Block"),
                ("""
                    MATCH (src:LoadParent {id: $source})
                    MATCH (tgt:Requirement {req_id: $target})
                    MERGE (src)-[r:SATISFIES]->(tgt)
                    RETURN src.id as src_id, tgt.req_id as tgt_id
                """, "SATISFIES", "LoadParent->Requirement"),
                ("""
                    MATCH (src:Requirement {req_id: $source})
                    MATCH (tgt:LoadParent {id: $target})
                    MERGE (tgt)-[r:SATISFIES]->(src)
                    RETURN src.req_id as src_id, tgt.id as tgt_id
                """, "SATISFIES", "Requirement->LoadParent"),
                ("""
                    MATCH (src:Block {sid: $source})
                    MATCH (tgt:Requirement {req_id: $target})
                    MERGE (src)-[r:SATISFIES]->(tgt)
                    RETURN src.sid as src_id, tgt.req_id as tgt_id
                """, "SATISFIES", "Block->Requirement"),
                ("""
                    MATCH (src:Requirement {req_id: $source})
                    MATCH (tgt:Block {sid: $target})
                    MERGE (tgt)-[r:SATISFIES]->(src)
                    RETURN src.req_id as src_id, tgt.sid as tgt_id
                """, "SATISFIES", "Requirement->Block"),
            ]
            
            for query, rel_type, description in connection_attempts:
                result = session.run(query, source=source, target=target).single()
                if result:
                    relationship_type = rel_type
                    print(f"Created {description}: {result['src_id']} -> {result['tgt_id']}")
                    break
            
            if not result:
                src_found = _find_node_types(session, source)
                tgt_found = _find_node_types(session, target)
                
                print(f"Source '{source}' found as: {src_found}")
                print(f"Target '{target}' found as: {tgt_found}")
                
                return jsonify({
                    "error": "Could not create connection - nodes not found or incompatible types",
                    "source": source,
                    "target": target,
                    "source_found": src_found,
                    "target_found": tgt_found
                }), 404
            
            _create_version_snapshots(session, source, target, relationship_type)
            
            return jsonify({
                "success": True,
                "message": f"Connected {source} to {target}",
                "source": source,
                "target": target,
                "relationship_type": relationship_type
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _find_node_types(session, node_id):
    """Find what type(s) a node ID matches."""
    result = session.run("""
        OPTIONAL MATCH (r:Requirement {req_id: $id}) 
        WITH CASE WHEN r IS NOT NULL THEN {type: 'Requirement', id: r.req_id, has_children: EXISTS((r)<-[:DERIVES_FROM]-())} ELSE NULL END as req
        OPTIONAL MATCH (b:Block {sid: $id})
        WITH req, CASE WHEN b IS NOT NULL THEN {type: 'Block', id: b.sid} ELSE NULL END as block
        OPTIONAL MATCH (l:LoadParent {id: $id})
        WITH req, block, CASE WHEN l IS NOT NULL THEN {type: 'LoadParent', id: l.id} ELSE NULL END as lp
        RETURN [x IN [req, block, lp] WHERE x IS NOT NULL] as found
    """, id=node_id).single()
    return result['found'] if result else []


@app.route('/api/node-type/<node_id>', methods=['GET'])
def get_node_type(node_id):
    """Get the type of a node and whether it has children."""
    try:
        with driver.session() as session:
            result = session.run("""
                OPTIONAL MATCH (r:Requirement {req_id: $id}) 
                WITH CASE WHEN r IS NOT NULL THEN {
                    type: 'Requirement', 
                    id: r.req_id, 
                    has_children: EXISTS((r)<-[:DERIVES_FROM]-())
                } ELSE NULL END as req
                OPTIONAL MATCH (b:Block {sid: $id})
                WITH req, CASE WHEN b IS NOT NULL THEN {
                    type: 'Block', 
                    id: b.sid,
                    parent_id: [(b)-[:BELONGS_TO]->(p:LoadParent) | p.id][0]
                } ELSE NULL END as block
                OPTIONAL MATCH (l:LoadParent {id: $id})
                WITH req, block, CASE WHEN l IS NOT NULL THEN {
                    type: 'LoadParent', 
                    id: l.id
                } ELSE NULL END as lp
                RETURN [x IN [req, block, lp] WHERE x IS NOT NULL] as found
            """, id=node_id).single()
            
            found = result['found'] if result else []
            if found:
                return jsonify(found[0])
            return jsonify({"error": "Node not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _create_version_snapshots(session, source, target, relationship_type):
    """Create version snapshots for both nodes involved in a connection."""
    import hashlib
    from datetime import datetime
    
    timestamp = datetime.utcnow().isoformat()

    for node_id in [source, target]:
        try:
            node_info = session. run("""
                MATCH (n)
                WHERE n.sid = $id OR n.req_id = $id OR n.id = $id
                RETURN labels(n) as labels,
                       coalesce(n.sid, n.req_id, n. id) as artifact_id,
                       n.name as name
            """, id=node_id).single()
            
            if not node_info:
                continue
            
            version_count = session.run("""
                MATCH (v:ArtifactVersion {artifact_id: $id})
                RETURN count(v) as count
            """, id=node_id). single()['count']
            
            new_version_num = version_count + 1
            artifact_id = node_info['artifact_id']
            
            snapshot = {
                "node_id": artifact_id,
                "name": node_info['name'],
                "change": {
                    "type": "connection_added",
                    "relationship": relationship_type,
                    "source": source,
                    "target": target,
                    "timestamp": timestamp
                }
            }
            
            snapshot_str = json.dumps(snapshot, sort_keys=True)
            version_hash = hashlib.sha256(snapshot_str.encode()).hexdigest()[:16]
            version_id = f"{artifact_id}_v{new_version_num}_{version_hash}"
            
            labels = node_info['labels']
            if 'Block' in labels or 'LoadParent' in labels:
                artifact_type = 'block'
                tool = 'simulink'
            else:
                artifact_type = 'requirement'
                tool = 'cameo'
            
            session.run("""
                MERGE (v:ArtifactVersion {version_id: $version_id})
                ON CREATE SET 
                    v.artifact_id = $artifact_id,
                    v.artifact_type = $artifact_type,
                    v.tool = $tool,
                    v.timestamp = $timestamp,
                    v.version_number = $version_num,
                    v.snapshot = $snapshot,
                    v.is_initial = false
            """, version_id=version_id, artifact_id=artifact_id,
                artifact_type=artifact_type, tool=tool, timestamp=timestamp,
                version_num=new_version_num, snapshot=snapshot_str)
            
            session.run("""
                MATCH (a) WHERE a.sid = $id OR a.req_id = $id OR a.id = $id
                MATCH (v:ArtifactVersion {version_id: $version_id})
                MERGE (a)-[:HAS_VERSION]->(v)
            """, id=node_id, version_id=version_id)
            
            print(f"Created version {version_id} for {node_id}")
            
        except Exception as e:
            print(f"Warning: Could not create version for {node_id}: {e}")


@app.route('/api/traceability/links', methods=['GET'])
def get_all_traceability_links():
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (block:LoadParent)-[:SATISFIES]->(req:Requirement)
                RETURN block.id as block_id,
                       block.name as block_name,
                       block.node_type as block_type,
                       req.req_id as req_id,
                       req.name as req_name,
                       req.node_type as req_type
                UNION
                MATCH (req:Requirement)-[:SATISFIES]->(block:LoadParent)
                RETURN block.id as block_id,
                       block.name as block_name,
                       block.node_type as block_type,
                       req.req_id as req_id,
                       req.name as req_name,
                       req.node_type as req_type
                UNION
                MATCH (block:Block)-[:SATISFIES]->(req:Requirement)
                RETURN block.sid as block_id,
                       block.name as block_name,
                       block.node_type as block_type,
                       req.req_id as req_id,
                       req.name as req_name,
                       req.node_type as req_type
                ORDER BY req_id, block_name
            """)
            
            links = []
            for record in result:
                links.append({
                    "requirement": {
                        "id": record['req_id'],
                        "name": record['req_name'],
                        "type": record['req_type']
                    },
                    "block": {
                        "sid": record['block_id'],
                        "name": record['block_name'],
                        "type": record['block_type']
                    },
                    "relationship": "SATISFIES"
                })
            
            return jsonify({
                "total_links": len(links),
                "links": links
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/traceability/stats', methods=['GET'])
def get_traceability_stats():
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (req:Requirement)
                OPTIONAL MATCH (block:Block)-[:SATISFIES]->(req)
                WITH count(DISTINCT req) as total_reqs,
                     count(DISTINCT CASE WHEN block IS NOT NULL THEN req END) as reqs_with_impl
                MATCH (b:Block)
                OPTIONAL MATCH (b)-[:SATISFIES]->(r:Requirement)
                RETURN total_reqs,
                       reqs_with_impl,
                       count(DISTINCT b) as total_blocks,
                       count(DISTINCT CASE WHEN r IS NOT NULL THEN b END) as blocks_with_reqs
            """)
            
            stats = result.single()
            link_result = session.run("MATCH ()-[r:SATISFIES]->() RETURN count(r) as satisfies_links")
            links = link_result.single()['satisfies_links']
            
            return jsonify({
                "requirements": {
                    "total": stats['total_reqs'],
                    "with_implementations": stats['reqs_with_impl'],
                    "coverage_percent": round(100 * stats['reqs_with_impl'] / stats['total_reqs'], 1) if stats['total_reqs'] > 0 else 0
                },
                "blocks": {
                    "total": stats['total_blocks'],
                    "with_requirements": stats['blocks_with_reqs'],
                    "coverage_percent": round(100 * stats['blocks_with_reqs'] / stats['total_blocks'], 1) if stats['total_blocks'] > 0 else 0
                },
                "traceability_links": links
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/parents', methods=['GET'])
def get_parent_nodes():
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (p:LoadParent)
                OPTIONAL MATCH (b:Block)-[:BELONGS_TO]->(p)
                WITH p, count(b) as block_count
                RETURN p.id as id, 
                       p.filename as filename, 
                       p.created_at as created_at,
                       p.timestamp as timestamp,
                       block_count
                ORDER BY p.created_at DESC
            """)
            
            parents = []
            for record in result:
                parents.append({
                    "id": record["id"],
                    "filename": record["filename"],
                    "block_count": record["block_count"]
                })
            
            return jsonify(parents)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/parents/<parent_id>/blocks', methods=['GET'])
def get_parent_blocks(parent_id):
    """Get all blocks belonging to a specific parent node."""
    try:
        code_mappings = load_code_mappings()
        
        with driver.session() as session:
            roots = session.run("""
                MATCH (b:Block)-[:BELONGS_TO]->(p:LoadParent {id: $parent_id})
                WHERE NOT EXISTS {
                    MATCH (other:Block)-[:BELONGS_TO]->(p)
                    WHERE (other)-[:CONNECTS_TO]->(b) AND other <> b
                }
                RETURN DISTINCT b.sid AS sid
            """, parent_id=parent_id).data()

            all_nodes = {}
            trees = []
            for root in roots:
                tree = build_block_tree(session, root["sid"], all_nodes=all_nodes, code_mappings=code_mappings)
                if tree:
                    trees.append(tree)

            return jsonify(trees)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _create_derives_from(session, child_id: str, parent_id: str):
    session.run(
        """
        MATCH (c:Requirement {req_id: $child}), (p:Requirement {req_id: $parent})
        MERGE (c)-[:DERIVES_FROM]->(p)
        """,
        child=child_id, parent=parent_id
    )

def fix_requirement_relationships_from_json(json_path: str):
    if not os.path.exists(json_path):
        print(f"Warning: JSON file not found: {json_path}")
        return

    print("Fixing requirement relationships from JSON...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    nodes = data.get('nodes', {})

    with driver.session() as session:
        session.run("MATCH ()-[r:DERIVES_FROM]->() DELETE r")
        created = 0
        errors = []
        seen_relationships = set() 

        for req_id, info in nodes.items():
            # Only process incoming (parents) to avoid duplicates
            # incoming = parents (this req derives FROM them)
            for parent in info.get('incoming', []):
                parent_id = parent.get('id') if isinstance(parent, dict) else parent
                if parent_id:
                    # Create a unique key for this relationship
                    rel_key = (req_id, parent_id)
                    if rel_key not in seen_relationships:
                        seen_relationships.add(rel_key)
                        try:
                            _create_derives_from(session, req_id, parent_id)
                            created += 1
                        except Exception as e:
                            errors.append(f"{req_id} to {parent_id}: {e}")

        root_count = session.run(
            "MATCH (r:Requirement) WHERE NOT (r)-[:DERIVES_FROM]->() RETURN count(r)"
        ).single()[0]

        print(f"Success: Created {created} DERIVES_FROM relationships")
        print(f"Success: Found {root_count} root requirements")
        if errors:
            print(f"Warning: {len(errors)} errors (nodes may not exist in DB)")

@app.route('/api/requirements/fix-relationships', methods=['POST'])
def fix_requirement_relationships():
    json_path = "backend/cameo_integration/all_requirements_with_hierarchy.json"
    try:
        fix_requirement_relationships_from_json(json_path)
        return jsonify({"success": True, "message": "Relationships fixed from JSON"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/requirements/verify', methods=['GET'])
def verify_requirement_structure():
    try:
        with driver.session() as session:
            node_count = session.run("MATCH (r:Requirement) RETURN count(r)").single()[0]
            rel_count = session.run("MATCH ()-[r:DERIVES_FROM]->() RETURN count(r)").single()[0]
            roots = session.run("""
                MATCH (r:Requirement)
                WHERE NOT (r)-[:DERIVES_FROM]->()
                RETURN r.req_id, r.name ORDER BY r.req_id LIMIT 5
            """)
            root_list = [{"id": r["r.req_id"], "name": r["r.name"]} for r in roots]

            return jsonify({
                "total_requirements": node_count,
                "total_derives_from": rel_count,
                "sample_roots": root_list
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/versions/load', methods=['POST'])
def load_versions():
    """Load all artifact versions from versioning trackers to Neo4j."""
    try:
        from versioning_loader import load_all_versions_to_neo4j
        from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
        
        clear_first = request.json.get('clear_first', False) if request.json else False
        
        stats = load_all_versions_to_neo4j(
            NEO4J_URI,
            NEO4J_USER,
            NEO4J_PASSWORD,
            clear_first=clear_first
        )
        
        return jsonify({
            "success": True,
            "message": "Versions loaded successfully",
            "stats": stats
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@app.route('/api/versions/stats', methods=['GET'])
def get_version_stats():
    """Get statistics about artifact versions in the database."""
    try:
        with driver.session() as session:
            total = session.run("MATCH (v:ArtifactVersion) RETURN count(v) as count").single()[0]
            
            by_tool = session.run("""
                MATCH (v:ArtifactVersion)
                RETURN v.tool as tool, count(v) as count
                ORDER BY tool
            """)
            by_tool_dict = {r['tool']: r['count'] for r in by_tool}
            
            by_type = session.run("""
                MATCH (v:ArtifactVersion)
                RETURN v.artifact_type as type, count(v) as count
                ORDER BY type
            """)
            by_type_dict = {r['type']: r['count'] for r in by_type}
            
            artifacts = session.run("""
                MATCH (artifact)-[:HAS_VERSION]->(v:ArtifactVersion)
                RETURN count(distinct artifact) as count
            """).single()[0]
            
            return jsonify({
                "total_versions": total,
                "artifacts_with_versions": artifacts,
                "by_tool": by_tool_dict,
                "by_type": by_type_dict
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/artifacts/<artifact_id>/versions', methods=['GET'])
def get_artifact_versions(artifact_id):
    """Get all versions of a specific artifact by artifact_id property."""
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (v:ArtifactVersion {artifact_id: $id})
                RETURN v.version_id as version_id,
                       v.artifact_id as artifact_id,
                       v.artifact_type as type,
                       v.tool as tool,
                       v. timestamp as timestamp,
                       v. version_number as version_number,
                       v.parent_version_id as parent_version_id
                ORDER BY v.timestamp DESC
            """, id=artifact_id)
            
            versions = [dict(r) for r in result]
            
            return jsonify({
                "artifact_id": artifact_id,
                "versions": versions,
                "count": len(versions)
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/blocks/with-versions', methods=['GET'])
def get_blocks_with_versions():
    """Get all Simulink blocks with their version information."""
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (block:Block)-[:HAS_VERSION]->(v:ArtifactVersion)
                WHERE v.tool = 'simulink'
                RETURN block.sid as sid,
                       block.name as name,
                       block.node_type as type,
                       count(v) as version_count,
                       max(v.timestamp) as latest_version_time
                ORDER BY block.name
            """)
            
            blocks = [dict(r) for r in result]
            
            return jsonify({
                "blocks": blocks,
                "total": len(blocks)
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/requirements/with-versions', methods=['GET'])
def get_requirements_with_versions():
    """Get all CAMEO requirements with their version information."""
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (req:Requirement)-[:HAS_VERSION]->(v:ArtifactVersion)
                WHERE v.tool = 'cameo'
                RETURN req.req_id as req_id,
                       req.name as name,
                       req.node_type as type,
                       count(v) as version_count,
                       max(v.timestamp) as latest_version_time
                ORDER BY req.req_id
            """)
            
            requirements = [dict(r) for r in result]
            
            return jsonify({
                "requirements": requirements,
                "total": len(requirements)
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/versions/lineage/<artifact_id>', methods=['GET'])
def get_version_lineage(artifact_id):
    """Get the version history/lineage for an artifact."""
    try:
        with driver.session() as session:
            # Get all versions in lineage order
            result = session.run("""
                MATCH (artifact)-[:HAS_VERSION]->(v:ArtifactVersion)
                WHERE artifact.sid = $id OR artifact.req_id = $id
                WITH v
                ORDER BY v.timestamp ASC
                OPTIONAL MATCH (v)-[:DERIVED_FROM]->(parent:ArtifactVersion)
                RETURN v.version_id as version_id,
                       v.timestamp as timestamp,
                       v.artifact_type as artifact_type,
                       v.tool as tool,
                       parent.version_id as parent_version_id
            """, id=artifact_id)
            
            versions = [dict(r) for r in result]
            
            if not versions:
                return jsonify({"error": f"No version lineage found for {artifact_id}"}), 404
            
            # Build lineage tree
            lineage = {
                "artifact_id": artifact_id,
                "total_versions": len(versions),
                "versions": versions
            }
            
            return jsonify(lineage)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/versions/all', methods=['GET'])
def get_all_versions():
    """Get all versioning data in one response."""
    try:
        with driver.session() as session:
            total = session.run("MATCH (v:ArtifactVersion) RETURN count(v) as count").single()[0]
            by_tool = session.run("""
                MATCH (v:ArtifactVersion)
                RETURN v.tool as tool, count(v) as count
                ORDER BY tool
            """)
            by_tool_dict = {r['tool']: r['count'] for r in by_tool}
            
            # Get blocks with versions
            blocks = session.run("""
                MATCH (block:Block)-[:HAS_VERSION]->(v:ArtifactVersion)
                WHERE v.tool = 'simulink'
                RETURN block.sid as sid,
                       block.name as name,
                       block.node_type as type,
                       count(v) as version_count,
                       max(v.timestamp) as latest_version_time
                ORDER BY block.name
            """)
            blocks_list = [dict(r) for r in blocks]
            
            # Get requirements with versions
            requirements = session.run("""
                MATCH (req:Requirement)-[:HAS_VERSION]->(v:ArtifactVersion)
                WHERE v.tool = 'cameo'
                RETURN req.req_id as req_id,
                       req.name as name,
                       req.node_type as type,
                       count(v) as version_count,
                       max(v.timestamp) as latest_version_time
                ORDER BY req.req_id
            """)
            requirements_list = [dict(r) for r in requirements]
            
            return jsonify({
                "stats": {
                    "total_versions": total,
                    "by_tool": by_tool_dict
                },
                "blocks": blocks_list,
                "requirements": requirements_list
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/connections/<model_name>', methods=['GET'])
def get_model_connections(model_name):
    """Get all current connections for a model."""
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (src:Block)-[r:CONNECTS_TO]->(dst:Block)
                RETURN src.sid as src_sid,
                       src.name as src_name,
                       dst.sid as dst_sid,
                       dst.name as dst_name,
                       r.created_at as created_at,
                       r.last_seen as last_seen,
                       r.version_id as version_id
            """)
            
            connections = [dict(r) for r in result]
            
            return jsonify({
                "model_name": model_name,
                "connection_count": len(connections),
                "connections": connections
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/connections/<model_name>/history', methods=['GET'])
def get_connection_history(model_name):
    """Get connection history (versions) for a model."""
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (cv:ConnectionVersion {model_id: $model_id})
                RETURN cv.version_id as version_id,
                       cv.timestamp as timestamp,
                       cv.connection_count as count,
                       cv.connections_hash as hash
                ORDER BY cv.timestamp DESC
            """, model_id=model_name)
            
            versions = [dict(r) for r in result]
            
            return jsonify({
                "model_name": model_name,
                "version_count": len(versions),
                "versions": versions
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/complete', methods=['GET'])
def get_complete_data():
    """Get ALL data: blocks, connections, versions, requirements in one response."""
    try:
        with driver.session() as session:
            # Get version stats
            total_versions = session.run("MATCH (v:ArtifactVersion) RETURN count(v) as count").single()[0]
            by_tool = session.run("""
                MATCH (v:ArtifactVersion)
                RETURN v.tool as tool, count(v) as count
                ORDER BY tool
            """)
            by_tool_dict = {r['tool']: r['count'] for r in by_tool}
            
            # Get blocks with versions
            blocks = session.run("""
                MATCH (block:Block)-[:HAS_VERSION]->(v:ArtifactVersion)
                WHERE v.tool = 'simulink'
                RETURN block.sid as sid,
                       block.name as name,
                       block.node_type as type,
                       count(v) as version_count,
                       max(v.timestamp) as latest_version_time
                ORDER BY block.name
            """)
            blocks_list = [dict(r) for r in blocks]
            
            # Get requirements with versions
            requirements = session.run("""
                MATCH (req:Requirement)-[:HAS_VERSION]->(v:ArtifactVersion)
                WHERE v.tool = 'cameo'
                RETURN req.req_id as req_id,
                       req.name as name,
                       req.node_type as type,
                       count(v) as version_count,
                       max(v.timestamp) as latest_version_time
                ORDER BY req.req_id
            """)
            requirements_list = [dict(r) for r in requirements]
            
            # Get all connections
            connections = session.run("""
                MATCH (src:Block)-[r:CONNECTS_TO]->(dst:Block)
                RETURN src.sid as src_sid,
                       src.name as src_name,
                       dst.sid as dst_sid,
                       dst.name as dst_name,
                       r.created_at as created_at,
                       r.last_seen as last_seen,
                       r.version_id as version_id
                ORDER BY src_name, dst_name
            """)
            connections_list = [dict(r) for r in connections]
            
            # Get connection versions
            conn_versions = session.run("""
                MATCH (cv:ConnectionVersion)
                RETURN cv.model_id as model_id,
                       cv.version_id as version_id,
                       cv.timestamp as timestamp,
                       cv.connection_count as count
                ORDER BY cv.model_id, cv.timestamp DESC
            """)
            conn_versions_list = [dict(r) for r in conn_versions]
            
            return jsonify({
                "stats": {
                    "total_versions": total_versions,
                    "total_blocks": len(blocks_list),
                    "total_requirements": len(requirements_list),
                    "total_connections": len(connections_list),
                    "by_tool": by_tool_dict
                },
                "blocks": blocks_list,
                "requirements": requirements_list,
                "connections": connections_list,
                "connection_versions": conn_versions_list
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def fix_relationships_on_startup():
    json_path = "backend/cameo_integration/all_requirements_with_hierarchy.json"
    fix_requirement_relationships_from_json(json_path)

@app. route('/api/artifacts/<artifact_id>/snapshot', methods=['POST'])
def create_artifact_snapshot(artifact_id):
    """Create a new version snapshot for an artifact after changes."""
    try:
        import hashlib
        from datetime import datetime
        
        with driver.session() as session:
            artifact = session.run("""
                MATCH (b:Block {sid: $id})
                RETURN 'block' as type, 'simulink' as tool, properties(b) as props
                UNION
                MATCH (r:Requirement {req_id: $id})
                RETURN 'requirement' as type, 'cameo' as tool, properties(r) as props
            """, id=artifact_id). single()
            
            if not artifact:
                return jsonify({"error": "Artifact not found"}), 404
            
            version_count = session.run("""
                MATCH (a)-[:HAS_VERSION]->(v:ArtifactVersion)
                WHERE a.sid = $id OR a.req_id = $id
                RETURN count(v) as count
            """, id=artifact_id). single()['count']
            
            new_version_num = version_count + 1
            timestamp = datetime.utcnow().isoformat()
            props_str = json. dumps(dict(artifact['props']), sort_keys=True)
            version_hash = hashlib.sha256(props_str.encode()).hexdigest()[:16]
            version_id = f"{artifact_id}_v{new_version_num}_{version_hash}"
            
            prev_version = session.run("""
                MATCH (a)-[:HAS_VERSION]->(v:ArtifactVersion)
                WHERE a.sid = $id OR a. req_id = $id
                RETURN v.version_id as vid
                ORDER BY v.timestamp DESC LIMIT 1
            """, id=artifact_id).single()
            
            if artifact['type'] == 'block':
                session.run("""
                    MATCH (b:Block {sid: $sid})
                    CREATE (v:ArtifactVersion {
                        version_id: $version_id,
                        artifact_id: $sid,
                        artifact_type: 'block',
                        tool: 'simulink',
                        timestamp: $timestamp,
                        version_number: $version_num,
                        snapshot: $snapshot
                    })
                    MERGE (b)-[:HAS_VERSION]->(v)
                """, sid=artifact_id, version_id=version_id, 
                    timestamp=timestamp, version_num=new_version_num, 
                    snapshot=props_str)
            else:
                session.run("""
                    MATCH (r:Requirement {req_id: $req_id})
                    CREATE (v:ArtifactVersion {
                        version_id: $version_id,
                        artifact_id: $req_id,
                        artifact_type: 'requirement',
                        tool: 'cameo',
                        timestamp: $timestamp,
                        version_number: $version_num,
                        snapshot: $snapshot
                    })
                    MERGE (r)-[:HAS_VERSION]->(v)
                """, req_id=artifact_id, version_id=version_id,
                    timestamp=timestamp, version_num=new_version_num,
                    snapshot=props_str)
            
            if prev_version:
                session.run("""
                    MATCH (new:ArtifactVersion {version_id: $new_id})
                    MATCH (prev:ArtifactVersion {version_id: $prev_id})
                    MERGE (new)-[:DERIVED_FROM]->(prev)
                """, new_id=version_id, prev_id=prev_version['vid'])
            
            return jsonify({
                "success": True,
                "version_id": version_id,
                "version_number": new_version_num,
                "timestamp": timestamp
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app. route('/api/versions/<version_id>/snapshot', methods=['GET'])
def get_version_snapshot(version_id):
    """Get the full snapshot data for a specific version."""
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (v:ArtifactVersion)
                WHERE v. version_id = $version_id 
                   OR v.connections_hash = $version_id
                RETURN v. artifact_id as artifact_id,
                       v. artifact_type as artifact_type,
                       v. tool as tool,
                       v.timestamp as timestamp,
                       v.version_number as version_number,
                       v.snapshot as snapshot,
                       v.is_initial as is_initial,
                       v.version_id as version_id
            """, version_id=version_id). single()
            
            if not result:
                result = session.run("""
                    MATCH (cv:ConnectionVersion)
                    WHERE cv. version_id = $version_id 
                       OR cv.connections_hash = $version_id
                    RETURN cv.model_id as artifact_id,
                           'connection' as artifact_type,
                           'simulink' as tool,
                           cv.timestamp as timestamp,
                           cv.connection_count as version_number,
                           cv. connections_hash as snapshot,
                           false as is_initial,
                           cv. version_id as version_id
                """, version_id=version_id).single()
            
            if not result:
                return jsonify({"error": "Version not found", "searched_id": version_id}), 404
            
            snapshot_data = {}
            if result['snapshot']:
                try:
                    import json
                    snapshot_data = json. loads(result['snapshot'])
                except (json.JSONDecodeError, TypeError):
                    snapshot_data = {"raw": result['snapshot']}
            
            return jsonify({
                "version_id": result['version_id'],
                "artifact_id": result['artifact_id'],
                "artifact_type": result['artifact_type'],
                "tool": result['tool'],
                "timestamp": result['timestamp'],
                "version_number": result['version_number'],
                "is_initial": result['is_initial'] or False,
                "snapshot": snapshot_data
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    fix_relationships_on_startup()
    app.run(host="0.0.0.0", port=5000, debug=True)