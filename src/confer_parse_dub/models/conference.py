"""Pydantic models for the conference registry file."""

from pydantic import BaseModel, Field


class ConferenceEntry(BaseModel):
    # Short name used as the invoke task name and directory (e.g., "chi2025").
    name: str
    # Human-readable label shown in task descriptions (e.g., "CHI 2025").
    label: str
    # Path to the conference config YAML file.
    config: str
    # True once analysis is complete and the conference will not be revisited.
    complete: bool = False


class ConferenceRegistry(BaseModel):
    """Shape of conferences.yml (root document)."""

    conferences: list[ConferenceEntry] = Field(default_factory=list)
