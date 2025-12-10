# backend/versioning/simulink_tracker.py
import json
from pathlib import Path
from typing import Dict, Tuple
from version_storage import VersionStorage
from enums import ArtifactType, Tool
from versioning.schema import ArtifactVersion, compute_artifact_hash, create_artifact_version


def track_simulink_blocks() -> Tuple[Dict[str, ArtifactVersion], int, int]:
    print(f"\n{'='*70}")
    print("TRACKING SIMULINK BLOCKS")
    print(f"{'='*70}")

    base_dir = Path("simulink_models")

    if not base_dir.exists():
        print("  simulink_models directory not found.")
        return {}, 0, 0

    connectivity_files = list(base_dir.rglob("block_connectivity.json"))

    if not connectivity_files:
        print("  No block_connectivity.json files found.")
        return {}, 0, 0

    print(f"  Found {len(connectivity_files)} Simulink model(s).")

    all_versions: Dict[str, ArtifactVersion] = {}
    total_new = total_changed = 0

    for connectivity_file in connectivity_files:
        model_name = connectivity_file.parent.parent.name
        print(f"\n  Processing model: {model_name}")

        with open(connectivity_file, "r") as f:
            data = json.load(f)

        blocks = data.get("nodes", {})
        if not blocks:
            print("   No blocks found in file.")
            continue

        version_file = Path(f"simulink_models/{model_name}/simulink_versions.json")
        previous_versions = VersionStorage.load(version_file)

        current_versions: Dict[str, ArtifactVersion] = {}

        for block_id, block_data in blocks.items():
            current_hash = compute_artifact_hash(block_data)
            prev_version = previous_versions.get(block_id)
            parent_id = prev_version.version_id if prev_version else None

            if prev_version and prev_version.version_id == current_hash:
                current_versions[block_id] = prev_version
                continue

            if prev_version:
                print(f"    CHANGED: {block_id}")
                total_changed += 1
            else:
                print(f"    NEW: {block_id}")
                total_new += 1

            version = create_artifact_version(
                block_id,
                block_data,
                ArtifactType.MODEL,
                Tool.SIMULINK,
                parent_id,
            )
            current_versions[block_id] = version
            all_versions[block_id] = version

        VersionStorage.save(version_file, current_versions)

    return all_versions, total_new, total_changed