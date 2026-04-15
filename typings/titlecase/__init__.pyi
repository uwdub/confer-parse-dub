from collections.abc import Callable

def titlecase(
    text: str,
    callback: Callable[[str, str, bool], str] | None = None,
    small_first_last: bool = True,
    preserve_blank_lines: bool = False,
) -> str: ...
