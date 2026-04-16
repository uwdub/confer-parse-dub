"""Core abstractions: RunContext, UI, UIChoice, and the Step base class."""

from __future__ import annotations

import pathlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from confer_parse_dub.browser_companion import BrowserCompanion
    from confer_parse_dub.config_document import ConfigDocument
    from confer_parse_dub.models.paper import ParsedPaper
    from confer_parse_dub.models.state import ProcessingState


@dataclass
class UIChoice:
    """A single option in a select or checkbox prompt."""

    title: str
    value: str | None = None  # returned value; defaults to title if None
    shortcut_key: str | None = None
    checked: bool = False  # initial checked state for checkbox


class UI(ABC):
    """Abstract user interface — implemented by CLI, web, AI, etc."""

    @abstractmethod
    def select(self, prompt: str, choices: list[UIChoice]) -> str | None:
        """Single-choice selection.  Returns the chosen value (or title), or None on abort."""
        ...

    @abstractmethod
    def confirm(self, prompt: str, default: bool = True) -> bool | None:
        """Yes/no prompt.  Returns True/False, or None on abort."""
        ...

    @abstractmethod
    def text(self, prompt: str, default: str = "") -> str | None:
        """Free-text input.  Returns the entered text, or None on abort."""
        ...

    @abstractmethod
    def autocomplete(self, prompt: str, choices: list[str]) -> str | None:
        """Autocomplete input.  Returns the entered/selected text, or None on abort."""
        ...

    @abstractmethod
    def checkbox(self, prompt: str, choices: list[UIChoice]) -> list[str] | None:
        """Multi-choice checkbox.  Returns list of selected values (or titles), or None on abort."""
        ...

    @abstractmethod
    def print(self, message: str = "") -> None:
        """Display a message."""
        ...


@dataclass
class RunContext:
    """Mutable shared state threaded through the step queue."""

    config_doc: ConfigDocument
    state: ProcessingState
    path_state: pathlib.Path
    ui: UI
    papers: list[ParsedPaper] = field(default_factory=list)
    total_loaded: int = 0  # set by LoadPapersStep, used by FilterSummaryStep
    review_skipped: bool = False
    browser: BrowserCompanion | None = None


class Step(ABC):
    """A unit of pipeline work.  Returns new steps to prepend to the queue."""

    @abstractmethod
    def execute(self, context: RunContext) -> list[Step]:
        """
        Execute this step.

        Returns a list of steps to prepend to the queue (depth-first execution).
        Raise QuitRequested to abort the pipeline cleanly.
        """
        ...
