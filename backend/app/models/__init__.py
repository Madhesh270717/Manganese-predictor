"""SQLAlchemy ORM models for Spotter AI.

Importing this package registers every model with Base.metadata so Alembic
autogenerate and the ORM can see the full schema.
"""

from app.models.base import Base, TimestampMixin
from app.models.blasting import Blasting
from app.models.data_source_metadata import DataSourceMetadata
from app.models.enums import ConfidenceLevel, ScheduleStatus, SourceType
from app.models.equipment import Equipment
from app.models.equipment_status_history import EquipmentStatusHistory
from app.models.exploration import Exploration
from app.models.zone_terrain_access import ZoneTerrainAccess
from app.models.geochemical import Geochemical
from app.models.geological import Geological
from app.models.mining_schedule import MiningSchedule
from app.models.production import Production
from app.models.satellite import Satellite
from app.models.weather import Weather
from app.models.zones import Zone

__all__ = [
    "Base",
    "TimestampMixin",
    "Zone",
    "Geological",
    "Geochemical",
    "Exploration",
    "Satellite",
    "Weather",
    "Production",
    "Equipment",
    "EquipmentStatusHistory",
    "ZoneTerrainAccess",
    "Blasting",
    "MiningSchedule",
    "DataSourceMetadata",
    "SourceType",
    "ConfidenceLevel",
    "ScheduleStatus",
]
