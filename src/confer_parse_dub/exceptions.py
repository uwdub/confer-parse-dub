"""Shared exceptions for the confer-parse-dub pipeline."""


class QuitRequested(Exception):
    """Raised when the user explicitly chooses to quit the interactive session."""


class ConfigError(Exception):
    """Raised when a config invariant is violated — either on load or during a mutation."""
