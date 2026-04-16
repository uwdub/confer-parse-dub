"""Load and save the conference registry."""

import pathlib

from confer_parse_dub_paths import PATH_DATA
from ruamel.yaml import YAML

from confer_parse_dub.models.conference import ConferenceEntry, ConferenceRegistry

_PATH_CONFERENCES = PATH_DATA / "conferences.yml"


def load_conferences(
    path: pathlib.Path = _PATH_CONFERENCES,
) -> list[ConferenceEntry]:
    """Load the conference registry, returning an empty list if not found."""
    if not path.exists():
        return []

    yaml = YAML()
    with open(path, "r", encoding="utf-8") as f:
        doc = yaml.load(f)

    return ConferenceRegistry.model_validate(doc or {}).conferences


def save_conferences(
    conferences: list[ConferenceEntry],
    path: pathlib.Path = _PATH_CONFERENCES,
) -> None:
    """Save the conference registry."""
    yaml = YAML()
    yaml.default_flow_style = False

    doc = ConferenceRegistry(conferences=conferences).model_dump()

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        _ = yaml.dump(doc, f)
