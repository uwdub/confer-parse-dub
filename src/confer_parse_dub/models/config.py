"""Pydantic models for the conference configuration file."""

from typing import Any, Literal, override

from pydantic import BaseModel, Field


class CommentedModel(BaseModel):
    """Base for all config models — any instance can carry an optional YAML comment."""

    comment: str | None = Field(default=None, exclude=True)

    def sort_key(self) -> Any:
        """Return a sort key for stable ordering in serialized output."""
        return ()


class TrackRule(CommentedModel):
    """A track in the query, identified by both its numeric ID and its human-readable name."""

    id: int
    name: str

    @override
    def sort_key(self) -> Any:
        return self.id


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

    @override
    def sort_key(self) -> Any:
        return (sorted(self.keywords)[:1], sorted(t.id for t in self.tracks)[:1])


class InstitutionRule(CommentedModel):
    """An institution explicitly included or excluded during affiliation review."""

    name: str

    @override
    def sort_key(self) -> Any:
        return self.name


class ManualSplitRule(CommentedModel):
    """
    An explicit split of one affiliation value into named parts.

    Used when no delimiter character in the value indicates a split is wanted,
    so the user manually specifies the resulting parts.
    """

    name: str
    parts: list[str]

    @override
    def sort_key(self) -> Any:
        return self.name


class DslRule(CommentedModel):
    """A DSL value explicitly included or excluded during affiliation review."""

    name: str

    @override
    def sort_key(self) -> Any:
        return self.name


class PaperRule(CommentedModel):
    """A paper explicitly included or excluded by ID for case-by-case corrections."""

    id: int

    @override
    def sort_key(self) -> Any:
        return self.id


class NameMatch(CommentedModel):
    name: str


class NameEntry(CommentedModel):
    name: str
    match: list[NameMatch] = []

    @override
    def sort_key(self) -> Any:
        return self.name


class AffiliationPatternItem(CommentedModel):
    institution: str | None = None
    dsl: str | None = None


class AffiliationMatchRule(CommentedModel):
    name: str | None = None
    affiliations: list[AffiliationPatternItem] = []

    @override
    def sort_key(self) -> Any:
        first = self.affiliations[0] if self.affiliations else None
        return (first.institution or "" if first else "", first.dsl or "" if first else "")


class RejectRule(CommentedModel):
    name: str | None = None


class AffiliationEntry(CommentedModel):
    canonical: str
    match: list[AffiliationMatchRule] = []
    match_for_name: list[AffiliationMatchRule] = []
    reject: list[RejectRule] = []

    @override
    def sort_key(self) -> Any:
        return self.canonical


class Config(BaseModel):
    version: Literal["v1"]
    file_input: str
    file_output: str
    query: list[QueryRule] = []
    include_institution: list[InstitutionRule] = []
    exclude_institution: list[InstitutionRule] = []
    split_institution: list[InstitutionRule] = []
    no_split_institution: list[InstitutionRule] = []
    manual_split_institution: list[ManualSplitRule] = []
    include_dsl: list[DslRule] = []
    exclude_dsl: list[DslRule] = []
    split_dsl: list[DslRule] = []
    no_split_dsl: list[DslRule] = []
    manual_split_dsl: list[ManualSplitRule] = []
    include_paper: list[PaperRule] = []
    exclude_paper: list[PaperRule] = []
    names: list[NameEntry] = []
    internal_affiliations: list[AffiliationEntry] = []
    external_affiliations: list[AffiliationEntry] = []
