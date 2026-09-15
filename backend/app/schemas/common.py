from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CreateSchema(BaseSchema):
    """Marker base for create/insert variants."""


class ReadSchema(BaseSchema):
    """Marker base for read/response variants."""
