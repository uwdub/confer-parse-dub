"""Pydantic models for parsed and processed conference papers."""

from pydantic import BaseModel


class Affiliation(BaseModel):
    institution: str = ""
    dsl: str = ""
    city: str = ""
    state: str = ""
    country: str = ""


class ParsedAuthor(BaseModel):
    name: str
    affiliations: list[Affiliation] = []
    # Set during affiliation normalization.
    canonical_affiliations: list[str] = []


class ParsedPaper(BaseModel):
    id: int
    title: str
    trackId: int | None = None
    track_name: str | None = None
    typeId: int | None = None
    sessionIds: list[int] = []
    eventIds: list[int] = []
    recognitionIds: list[int] = []
    importedId: str = ""
    source: str = ""
    isBreak: bool = False
    addons: dict[str, object] = {}
    bestpaper: bool = False
    honorablemention: bool = False
    authors: list[ParsedAuthor] = []
