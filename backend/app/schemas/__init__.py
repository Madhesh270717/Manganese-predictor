"""Pydantic schemas for Spotter AI — mirror the SQLAlchemy models.

Conventions:
- ``*Create``  — input schemas for inserts
- ``*Read``    — output schemas for API responses
- Geometry fields are WKT strings (SRID 4326) so they serialize cleanly
  through JSON APIs; the ORM models store them as PostGIS geometry types.
"""

from app.schemas.blasting import BlastingCreate, BlastingRead
from app.schemas.common import BaseSchema, CreateSchema, ReadSchema
from app.schemas.data_source_metadata import (
    DataSourceMetadataCreate,
    DataSourceMetadataRead,
)
from app.schemas.equipment import EquipmentCreate, EquipmentRead
from app.schemas.exploration import ExplorationCreate, ExplorationRead
from app.schemas.geochemical import GeochemicalCreate, GeochemicalRead
from app.schemas.geological import GeologicalCreate, GeologicalRead
from app.schemas.mining_schedule import MiningScheduleCreate, MiningScheduleRead
from app.schemas.production import ProductionCreate, ProductionRead
from app.schemas.satellite import SatelliteCreate, SatelliteRead
from app.schemas.weather import WeatherCreate, WeatherRead
from app.schemas.zones import ZoneCreate, ZoneRead

__all__ = [
    "BaseSchema",
    "CreateSchema",
    "ReadSchema",
    "ZoneCreate",
    "ZoneRead",
    "GeologicalCreate",
    "GeologicalRead",
    "GeochemicalCreate",
    "GeochemicalRead",
    "ExplorationCreate",
    "ExplorationRead",
    "SatelliteCreate",
    "SatelliteRead",
    "WeatherCreate",
    "WeatherRead",
    "ProductionCreate",
    "ProductionRead",
    "EquipmentCreate",
    "EquipmentRead",
    "BlastingCreate",
    "BlastingRead",
    "MiningScheduleCreate",
    "MiningScheduleRead",
    "DataSourceMetadataCreate",
    "DataSourceMetadataRead",
]
