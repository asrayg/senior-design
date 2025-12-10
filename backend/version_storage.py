# backend/version_storage.py
import json
from pathlib import Path
from typing import Dict
from versioning.schema import ArtifactVersion

class VersionStorage:
    @staticmethod
    def load(file_path: Path) -> Dict[str, ArtifactVersion]:
        if not file_path.exists():
            return {}
        with open(file_path, "r") as f:
            raw = json.load(f)
        return {k: ArtifactVersion.from_dict(v) for k, v in raw.items()}

    @staticmethod
    def save(file_path: Path, versions: Dict[str, ArtifactVersion]):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump({k: v.to_dict() for k, v in versions.items()}, f, indent=2)