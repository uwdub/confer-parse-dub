"""Pydantic models for the conference configuration file."""

from typing import Literal

from pydantic import BaseModel, Field


class CommentedModel(BaseModel):
    """Base for all config models — any instance can carry an optional YAML comment."""

    comment: str | None = Field(default=None, exclude=True)


class TrackRule(CommentedModel):
    """A track in the query, identified by both its numeric ID and its human-readable name."""

    id: int
    name: str


class QueryRule(CommentedModel):
    """
    A search query: one or more keywords matched against any selected track.

    Keywords are checked (case-insensitive substring) against both the
    institution and dsl fields of each author affiliation.  A paper matches
    if it is in one of the listed tracks AND at least one author affiliation
    matches at least one keyword.
    """

    keywords: list[str] = []
    tracks: list[TrackRule] = []


class InstitutionRule(CommentedModel):
    """An institution explicitly included or excluded during affiliation review."""

    name: str


class DslRule(CommentedModel):
    """A DSL value explicitly included or excluded during affiliation review."""

    name: str


class PaperRule(CommentedModel):
    """A paper explicitly included or excluded by ID for case-by-case corrections."""

    id: int


class NameMatch(CommentedModel):
    name: str


class NameEntry(CommentedModel):
    name: str
    match: list[NameMatch] = []


class AffiliationPatternItem(CommentedModel):
    institution: str | None = None
    dsl: str | None = None


class AffiliationMatchRule(CommentedModel):
    name: str | None = None
    affiliations: list[AffiliationPatternItem] = []


class RejectRule(CommentedModel):
    name: str | None = None


class AffiliationEntry(CommentedModel):
    canonical: str
    match: list[AffiliationMatchRule] = []
    reject: list[RejectRule] = []


class Config(BaseModel):
    version: Literal["v1"]
    file_input: str
    file_output: str
    query: list[QueryRule] = []
    include_institution: list[InstitutionRule] = []
    exclude_institution: list[InstitutionRule] = []
    include_dsl: list[DslRule] = []
    exclude_dsl: list[DslRule] = []
    include_paper: list[PaperRule] = []
    exclude_paper: list[PaperRule] = []
    names: list[NameEntry] = []
    internal_affiliations: list[AffiliationEntry] = []
    external_affiliations: list[AffiliationEntry] = []
