"""Raw Pydantic models for the SIGCHI program JSON (schemeVersion 7)."""

from typing import Literal

from pydantic import BaseModel


class RawAffiliationInput(BaseModel):
    institution: str = ""
    dsl: str = ""
    city: str = ""
    state: str = ""
    country: str = ""


class RawAuthorInput(BaseModel):
    personId: int
    affiliations: list[RawAffiliationInput] = []


class RawPersonInput(BaseModel):
    id: int
    firstName: str = ""
    lastName: str = ""
    middleInitial: str = ""
    importedId: str = ""
    source: str = ""


class RawVideoInput(BaseModel):
    type: str = ""
    url: str = ""


class RawAddonInput(BaseModel):
    name: str = ""
    title: str = ""
    type: str = ""
    url: str = ""


class RawContentInput(BaseModel):
    id: int
    typeId: int | None = None
    trackId: int | None = None
    title: str = ""
    isBreak: bool = False
    importedId: str = ""
    source: str = ""
    award: str = ""
    sessionIds: list[int] = []
    eventIds: list[int] = []
    recognitionIds: list[int] = []
    addons: dict[str, RawAddonInput] = {}
    authors: list[RawAuthorInput] = []


class RawTrackInput(BaseModel):
    id: int
    name: str = ""


class RawProgramInput(BaseModel):
    schemeVersion: Literal[7]
    tracks: list[RawTrackInput] = []
    contents: list[RawContentInput] = []
    people: list[RawPersonInput] = []
