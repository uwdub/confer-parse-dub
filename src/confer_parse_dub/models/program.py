"""Raw Pydantic models for the SIGCHI program JSON (schemeVersion 7)."""

from pydantic import BaseModel, model_validator


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


class RawContentInput(BaseModel):
    id: int
    typeId: int | None = None
    trackId: int | None = None
    title: str = ""
    isBreak: bool = False
    importedId: str = ""
    source: str = ""
    award: str = ""
    doi: str | None = None
    sessionIds: list[int] = []
    eventIds: list[int] = []
    recognitionIds: list[int] = []
    authors: list[RawAuthorInput] = []
    videos: list[RawVideoInput] = []


class RawTrackInput(BaseModel):
    id: int
    name: str = ""


SUPPORTED_SCHEME_VERSION = 7


class RawProgramInput(BaseModel):
    schemeVersion: int
    tracks: list[RawTrackInput] = []
    contents: list[RawContentInput] = []
    people: list[RawPersonInput] = []

    @model_validator(mode="after")
    def check_scheme_version(self) -> "RawProgramInput":
        if self.schemeVersion != SUPPORTED_SCHEME_VERSION:
            raise ValueError(
                "Unsupported schemeVersion {!r} (expected {!r}).".format(
                    self.schemeVersion, SUPPORTED_SCHEME_VERSION
                )
            )
        return self
