"""Pydantic models for persisted processing state."""

from enum import Enum

from pydantic import BaseModel


class DecisionType(str, Enum):
    ADD_NAME = "add_name"
    ADD_NAME_ALIAS = "add_name_alias"
    SKIP_NAME = "skip_name"
    ADD_AFFILIATION = "add_affiliation"
    ADD_AFFILIATION_MATCH_RULE = "add_affiliation_match_rule"
    SKIP_AFFILIATION = "skip_affiliation"


class Decision(BaseModel):
    type: DecisionType
    # Human-readable summary shown when reviewing history.
    summary: str
    # Fields used to reverse the decision (only the relevant ones are populated).
    name: str | None = None  # raw name (add_name, add_name_alias, skip_name)
    canonical: str | None = (
        None  # canonical name/affiliation (alias and affiliation ops)
    )
    key: str | None = None  # state key (skip_affiliation)


class ProcessingState(BaseModel):
    # Raw names explicitly skipped by the user.
    skipped_names: list[str] = []
    # Keys (author_name::affiliation_fingerprint) explicitly skipped by the user.
    skipped_affiliations: list[str] = []
    # Keys auto-skipped because the author listed more than one affiliation.
    # These are not re-queued by --review-skipped and need dedicated follow-up.
    skipped_multi_affiliations: list[str] = []
    # Ordered log of decisions made, used for undo.
    history: list[Decision] = []
