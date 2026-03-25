"""Author name normalization — lookup only."""

from confer_parse_dub.models.config import Config


def find_canonical_name(config: Config, name: str) -> str | None:
    """Return the canonical name for a raw name, or None if unresolved."""
    for entry in config.names:
        if entry.name == name:
            return entry.name
        for m in entry.match:
            if m.name == name:
                return entry.name
    return None
