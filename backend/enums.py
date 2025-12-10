# backend/enums.py
from enum import Enum

class ArtifactType(Enum):
    REQUIREMENT = "requirement"
    MODEL = "model"

class Tool(Enum):
    CAMEO = "cameo"
    SIMULINK = "simulink"