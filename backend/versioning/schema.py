# backend/versioning/schema.py
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

@dataclass
class ArtifactVersion:
    artifact_id: str
    version_id: str
    artifact_type: str
    tool: str
    timestamp: str
    parent_version_id: Optional[str] = None
    snapshot: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "ArtifactVersion":
        return ArtifactVersion(**data)


def compute_artifact_hash(artifact_data: dict) -> str:
    """Compute a stable hash of artifact data."""
    data_str = json.dumps(artifact_data, sort_keys=True)
    return hashlib.sha256(data_str.encode("utf-8")).hexdigest()


def create_artifact_version(artifact_id, artifact_data, artifact_type, tool, parent_version_id=None):
    """Generate a new ArtifactVersion with snapshot data."""
    version_id = compute_artifact_hash(artifact_data)
    snapshot_str = json.dumps(artifact_data, sort_keys=True)
    return ArtifactVersion(
        artifact_id=artifact_id,
        version_id=version_id,
        artifact_type=artifact_type.value if hasattr(artifact_type, "value") else artifact_type,
        tool=tool.value if hasattr(tool, "value") else tool,
        timestamp=datetime.utcnow().isoformat(),
        parent_version_id=parent_version_id,
        snapshot=snapshot_str,
    )