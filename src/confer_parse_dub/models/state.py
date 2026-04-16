"""Pydantic models for persisted processing state."""

from enum import Enum

from pydantic import BaseModel

from confer_parse_dub.models.config import AffiliationMatchRule


class DecisionType(str, Enum):
    ADD_NAME = "add_name"
    ADD_NAME_ALIAS = "add_name_alias"
    SKIP_NAME = "skip_name"
    ADD_AFFILIATION = "add_affiliation"
    ADD_AFFILIATION_MATCH_RULE = "add_affiliation_match_rule"
    SKIP_AFFILIATION = "skip_affiliation"


class Decision(BaseModel):
    """
    One user decision recorded for display and undo.

    `summary` is always set. Other attributes are populated only for undo;
    which ones apply depends on `type`:

    - add_name: `name`.
    - add_name_alias: `name`, `canonical`.
    - skip_name: `name`.
    - add_affiliation: `canonical`.
    - add_affiliation_match_rule: `canonical`, `match_rule`.
    - skip_affiliation: `key`.

    A discriminated union of per-type models would encode this in the type
    system; we have not pursued that refactor.
    """

    type: DecisionType
    # Human-readable summary shown when reviewing history.
    summary: str
    # Fields used to reverse the decision (only the relevant ones are populated).
    name: str | None = None  # raw name (add_name, add_name_alias, skip_name)
    canonical: str | None = (
        None  # canonical name/affiliation (alias and affiliation ops)
    )
    key: str | None = None  # state key (skip_affiliation)
    # The exact rule added, stored so undo can remove it by content not position.
    match_rule: AffiliationMatchRule | None = None


class ProcessingState(BaseModel):
    # Raw names explicitly skipped by the user.
    skipped_names: list[str] = []
    # Keys (author_name::affiliation_fingerprint) explicitly skipped by the user.
    skipped_affiliations: list[str] = []
    # Ordered log of decisions made, used for undo.
    history: list[Decision] = []
