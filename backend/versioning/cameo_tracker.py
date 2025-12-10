# backend/versioning/cameo_tracker.py
import json
from pathlib import Path
from typing import Dict, Tuple
from version_storage import VersionStorage
from enums import ArtifactType, Tool
from versioning.schema import ArtifactVersion, compute_artifact_hash, create_artifact_version


def track_cameo_requirements() -> Tuple[Dict[str, ArtifactVersion], int, int]:
    print(f"\n{'='*70}")
    print("TRACKING CAMEO REQUIREMENTS")
    print(f"{'='*70}")

    req_file = Path("cameo_integration/all_requirements_with_hierarchy.json")
    if not req_file.exists():
        print("  File not found.")
        return {}, 0, 0

    with open(req_file, "r") as f:
        data = json.load(f)

    nodes = data.get("nodes", {})
    version_file = Path("cameo_integration/cameo_versions.json")
    previous_versions = VersionStorage.load(version_file)

    current_versions = {}
    new_count = changed_count = 0

    for artifact_id, artifact_data in nodes.items():
        current_hash = compute_artifact_hash(artifact_data)
        if artifact_id in previous_versions and previous_versions[artifact_id].version_id == current_hash:
            current_versions[artifact_id] = previous_versions[artifact_id]
            continue

        parent_id = previous_versions.get(artifact_id).version_id if artifact_id in previous_versions else None
        if artifact_id in previous_versions:
            print(f"  CHANGED: {artifact_id}")
            changed_count += 1
        else:
            print(f"  NEW: {artifact_id}")
            new_count += 1

        version = create_artifact_version(artifact_id, artifact_data, ArtifactType.REQUIREMENT, Tool.CAMEO, parent_id)
        current_versions[artifact_id] = version

    VersionStorage.save(version_file, current_versions)
    return current_versions, new_count, changed_count