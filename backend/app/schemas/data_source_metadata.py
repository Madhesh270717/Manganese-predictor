from datetime import datetime

from app.models.enums import ConfidenceLevel, SourceType
from app.schemas.common import CreateSchema, ReadSchema


class DataSourceMetadataCreate(CreateSchema):
    dataset_name: str
    source_type: SourceType
    confidence_level: ConfidenceLevel
    source_name: str
    last_updated: datetime


class DataSourceMetadataRead(ReadSchema):
    id: int
    dataset_name: str
    source_type: SourceType
    confidence_level: ConfidenceLevel
    source_name: str
    last_updated: datetime
    created_at: datetime
    updated_at: datetime
