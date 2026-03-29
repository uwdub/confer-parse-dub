"""Load and save processing state."""

import pathlib

from confer_parse_dub.models.state import ProcessingState


def load_state(path: pathlib.Path) -> ProcessingState:
    """Load state from JSON, returning empty state if the file does not exist."""
    if not path.exists():
        return ProcessingState()

    with open(path, "r", encoding="utf-8") as f:
        return ProcessingState.model_validate_json(f.read())


def save_state(state: ProcessingState, path: pathlib.Path) -> None:
    """Save state to JSON."""
    with open(path, "w", encoding="utf-8") as f:
        _ = f.write(state.model_dump_json(indent=2))
