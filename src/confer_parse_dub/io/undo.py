"""Undo the most recent decision recorded in processing state."""

import pathlib
from typing import TypeVar

from confer_parse_dub.config_document import ConfigDocument
from confer_parse_dub.exceptions import ConfigError
from confer_parse_dub.io.state_io import save_state
from confer_parse_dub.models.state import Decision, DecisionType, ProcessingState

T = TypeVar("T")


def _require(value: T | None, field: str, decision_type: DecisionType) -> T:
    """Return value or raise ConfigError if it is missing."""
    if value is None:
        raise ConfigError(
            "Decision of type '{}' is missing required field '{}'.".format(
                decision_type.value, field
            )
        )
    return value


def undo_last_decision(
    config_doc: ConfigDocument,
    state: ProcessingState,
    path_state: pathlib.Path,
) -> Decision | None:
    """
    Reverse the most recent decision and remove it from history.

    Returns the undone Decision, or None if history is empty.
    """
    if not state.history:
        return None

    decision = state.history[-1]

    match decision.type:
        case DecisionType.ADD_NAME:
            name = _require(decision.name, "name", decision.type)
            config_doc.remove_name(name)

        case DecisionType.ADD_NAME_ALIAS:
            canonical = _require(decision.canonical, "canonical", decision.type)
            name = _require(decision.name, "name", decision.type)
            config_doc.remove_name_alias(canonical, name)

        case DecisionType.SKIP_NAME:
            name = _require(decision.name, "name", decision.type)
            if name in state.skipped_names:
                state.skipped_names.remove(name)

        case DecisionType.ADD_AFFILIATION:
            canonical = _require(decision.canonical, "canonical", decision.type)
            config_doc.remove_affiliation(canonical)

        case DecisionType.ADD_AFFILIATION_MATCH_RULE:
            canonical = _require(decision.canonical, "canonical", decision.type)
            match_rule = _require(decision.match_rule, "match_rule", decision.type)
            config_doc.remove_affiliation_match_rule(canonical, match_rule)

        case DecisionType.SKIP_AFFILIATION:
            key = _require(decision.key, "key", decision.type)
            if key in state.skipped_affiliations:
                state.skipped_affiliations.remove(key)

    _ = state.history.pop()
    save_state(state, path_state)

    return decision
