#!/usr/bin/env python3


import os
import time
import threading
import json
from .cameo_processor import CameoProcessor
from .cameo_neo4j_loader import load_connectivity_json
from .config import LOCAL_REPO_PATH

def analyze_cameo_dir(model_dir: str):
    processor = CameoProcessor(model_dir)
    
    results = processor.process_all_files()
    if results:
        for stem, result in results.items():
            output_path = result["output_file"]
            with open(output_path, 'r') as f:
                json_data = json.load(f)
            node_count = load_connectivity_json(json_data)
            print(f"Loaded {node_count} nodes from {output_path} to Neo4j")

def find_mdzip_dirs(root_dir: str):
    """Yield directories that contain .mdzip files."""
    for current_dir, _subdirs, files in os.walk(root_dir):
        if any(f.endswith('.mdzip') for f in files):
            yield current_dir

def main():
    while True:
        try:
            mdzip_files = [f for f in os.listdir(LOCAL_REPO_PATH) if f.lower().endswith('.mdzip')]
            if mdzip_files:
                for mdzip_name in mdzip_files:
                    mdzip_path = os.path.join(LOCAL_REPO_PATH, mdzip_name)
                    dest_dir = os.path.join(LOCAL_REPO_PATH, os.path.splitext(mdzip_name)[0])
                    os.makedirs(dest_dir, exist_ok=True)  # Simulate extraction
                    for model_dir in find_mdzip_dirs(dest_dir):
                        analyze_cameo_dir(model_dir)
            else:
                for model_dir in find_mdzip_dirs(LOCAL_REPO_PATH):
                    analyze_cameo_dir(model_dir)
        except Exception as e:
            print("Error")
        time.sleep(60)

if __name__ == "__main__":
    sync_thread = threading.Thread(target=main, daemon=True)
    sync_thread.start()