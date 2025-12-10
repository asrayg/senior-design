from sync import sync_repo
import threading
from file_manager import init_folder, extract_zip
from simulink_analyzer import SimulinkAnalyzer, SlxcAnalyzer
from neo4j_loader import load_connectivity_json
from config import LOCAL_REPO_PATH, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
import os
import json
from endpoints import app
from connection_versioning import ConnectionVersioningLoader
from cameo_neo4j_loader import load_requirements_from_cameo
from versioning_loader import create_initial_snapshot


def analyze_model_dir(model_dir: str):
    analyzer = SimulinkAnalyzer(model_dir)
    analyzer.load_model()
    output_path = os.path.join(model_dir, "block_connectivity.json")
    analyzer.export_to_json(output_path)
   
    with open(output_path, 'r') as f:
        json_data = json.load(f)
    filename = os.path.basename(model_dir)
    node_count, parent_id = load_connectivity_json(json_data, filename)
    print(f"Loaded {node_count} nodes from {model_dir} to Neo4j (parent: {parent_id})")
   
    conn_loader = ConnectionVersioningLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    conn_loader.track_model_connections(filename, json_data)
    conn_loader.close()
    print(f"Tracked connections for {filename}")


def analyze_slxc_file(slxc_path: str):
    """Analyze a Simulink code generation file (.slxc) for code-to-model mappings.
    
    Extracts the .slxc file to a permanent directory for faster subsequent access.
    """
    analyzer = SlxcAnalyzer(slxc_path)
    # Keep extracted so the endpoint can read directly from disk
    if not analyzer.load_slxc(keep_extracted=True):
        print(f"Failed to load SLXC file: {slxc_path}")
        return None
    
    analyzer.analyze_code_mappings()
    
    # Export to JSON in the same directory as the slxc file
    output_dir = os.path.dirname(slxc_path)
    base_name = os.path.splitext(os.path.basename(slxc_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_code_mappings.json")
    
    mappings_data = analyzer.export_to_json(output_path)
    # Don't cleanup - keep extracted for fast access
    
    print(f"Analyzed SLXC file: {slxc_path}")
    print(f"  Found {len(mappings_data['mappings'])} block-to-code mappings")
    print(f"  Extracted to: {SlxcAnalyzer.get_extracted_dir(slxc_path)}")
    
    return mappings_data

def find_model_dirs(root_dir: str):
    for current_dir, _subdirs, files in os.walk(root_dir):
        if "blockdiagram.xml" in files:
            yield current_dir


def initial_sync():
    """Run the synchronization and analysis process once."""
    init_folder()
    try:
        sync_repo()
        
        # Process .slx files (Simulink models)
        slx_files = [f for f in os.listdir(LOCAL_REPO_PATH) if f.lower().endswith('.slx')]
        if slx_files:
            for zip_name in slx_files:
                zip_path = os.path.join(LOCAL_REPO_PATH, zip_name)
                dest_dir = os.path.join(LOCAL_REPO_PATH, os.path.splitext(zip_name)[0])
                extract_zip(zip_path, dest_dir)
                for model_dir in find_model_dirs(dest_dir):
                    analyze_model_dir(model_dir)
        else:
            for model_dir in find_model_dirs(LOCAL_REPO_PATH):
                analyze_model_dir(model_dir)
        
        # Process .slxc files (Simulink code generation artifacts)
        slxc_files = [f for f in os.listdir(LOCAL_REPO_PATH) if f.lower().endswith('.slxc')]
        for slxc_name in slxc_files:
            slxc_path = os.path.join(LOCAL_REPO_PATH, slxc_name)
            analyze_slxc_file(slxc_path)
            
    except Exception as e:
        print(f"Error during initial sync: {e}")

       
if __name__ == "__main__":
    from neo4j import GraphDatabase
    
    startup_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    def count_versions():
        with startup_driver.session() as session:
            return session.run("MATCH (v:ArtifactVersion) RETURN count(v) as count").single()['count']
    
    print("\n" + "="*70)
    print("STARTUP: CHECKING EXISTING VERSIONS")
    print("="*70)
    
    initial_count = count_versions()
    print(f"Found {initial_count} existing version snapshots")
    
    with startup_driver.session() as session:
        marker = session. run(
            "MATCH (m:VersioningMarker {id: 'initialized'}) RETURN m"
        ).single()
    
    versions_initialized = marker is not None or initial_count > 0
    
    if versions_initialized:
        print("Versioning system already initialized")
        print("Skipping initial_sync to preserve versions")
    else:
        initial_sync()
        print(f"Versions after initial_sync: {count_versions()}")
   
    print("\n" + "="*70)
    print("STARTING FLASK SERVER ON PORT 5000")
    print("="*70 + "\n")

    print("="*70)
    print("LOADING CAMEO REQUIREMENTS INTO NEO4J")
    print("="*70)

    json_path = "cameo_integration/all_requirements_with_hierarchy.json"

    try:
        load_requirements_from_cameo(
            json_path=json_path,
            uri=NEO4J_URI,
            user=NEO4J_USER,
            password=NEO4J_PASSWORD
        )
    except Exception as e:
        print(f"[CAMEO] Failed to load requirements: {e}")

    print("="*70)
    print("CHECKING VERSION SNAPSHOTS")
    print("="*70)
    
    final_count = count_versions()
    
    if not versions_initialized and final_count == 0:
        print("First time setup - creating initial snapshots...")
        try:
            create_initial_snapshot(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
            with startup_driver.session() as session:
                session.run(
                    "MERGE (m:VersioningMarker {id: 'initialized'}) "
                    "SET m.created_at = datetime()"
                )
            print("✓ Created initialization marker")
        except Exception as e:
            print(f"Warning: Could not create initial snapshot: {e}")
    else:
        print(f"✓ {final_count} versions preserved")
    
    startup_driver.close()
        
    print("="*70)
    print("ALL SYSTEMS READY")
    print("="*70)

    app.run(debug=True, port=5000, use_reloader=False)