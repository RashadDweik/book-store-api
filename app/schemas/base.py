"""Shared Pydantic base schema configuration."""

from pydantic import BaseModel, ConfigDict


class SchemaBase(BaseModel):
    """Enable ORM attribute access for response models."""
    model_config = ConfigDict(from_attributes=True)
