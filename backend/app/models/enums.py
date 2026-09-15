from enum import Enum


class SourceType(str, Enum):
    REAL = "real"
    SYNTHETIC = "synthetic"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    SYNTHETIC = "SYNTHETIC"


class ScheduleStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    COMPLETED = "completed"
