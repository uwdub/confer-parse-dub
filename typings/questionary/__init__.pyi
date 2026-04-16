"""Partial type stubs for questionary (only APIs used in this project).

Narrow types are chosen for our call sites. Parameters that map to prompt_toolkit
or open-ended library internals use ``object`` instead of ``Any`` so the checker
stays quiet; that is intentionally less precise than the real package.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Generic, TypeVar

_T = TypeVar("_T")

class Question(Generic[_T]):
    def ask(self, patch_stdout: bool = False, kbi_msg: str = ...) -> _T | None: ...

class Choice:
    title: str | list[tuple[str, str]] | None
    value: object
    disabled: str | None
    checked: bool
    description: str | None

    def __init__(
        self,
        title: str | list[tuple[str, str]] | None = None,
        value: object = None,
        disabled: str | None = None,
        checked: bool | None = False,
        shortcut_key: str | bool | None = True,
        description: str | None = None,
    ) -> None: ...

def select(
    message: str,
    choices: Sequence[str | Choice | dict[str, object]],
    default: str | Choice | dict[str, object] | None = None,
    *,
    qmark: str = ...,
    pointer: str | None = ...,
    style: object | None = None,
    use_shortcuts: bool = False,
    use_arrow_keys: bool = True,
    use_indicator: bool = False,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: bool = False,
    show_selected: bool = False,
    show_description: bool = True,
    instruction: str | None = None,
) -> Question[str]: ...
def confirm(
    message: str,
    default: bool = True,
    *,
    qmark: str = ...,
    style: object | None = None,
    auto_enter: bool = True,
    instruction: str | None = None,
) -> Question[bool]: ...
def text(
    message: str,
    default: str = "",
    validate: Callable[[str], bool | str] | None = None,
    *,
    qmark: str = ...,
    style: object | None = None,
    multiline: bool = False,
    instruction: str | None = None,
    lexer: object | None = None,
) -> Question[str]: ...
def autocomplete(
    message: str,
    choices: list[str],
    default: str = "",
    *,
    qmark: str = ...,
    completer: object | None = None,
    meta_information: dict[str, object] | None = None,
    ignore_case: bool = True,
    match_middle: bool = True,
    complete_style: object = ...,
    validate: Callable[[str], bool | str] | None = None,
    style: object | None = None,
) -> Question[str]: ...
def checkbox(
    message: str,
    choices: Sequence[str | Choice | dict[str, object]],
    default: str | None = None,
    validate: Callable[[list[str]], bool | str] | None = None,
    *,
    qmark: str = ...,
    pointer: str | None = ...,
    style: object | None = None,
    initial_choice: str | Choice | dict[str, object] | None = None,
    use_arrow_keys: bool = True,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
) -> Question[list[str]]: ...
