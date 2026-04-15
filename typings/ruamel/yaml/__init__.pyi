from __future__ import annotations

from typing import TextIO

from ruamel.yaml.comments import CommentedMap, CommentedSeq

YamlScalar = None | bool | int | float | str
YamlNode = CommentedMap | CommentedSeq | YamlScalar

class YAML:
    preserve_quotes: bool
    default_flow_style: bool

    def __init__(self, *, typ: str | None = None, pure: bool = False) -> None: ...
    def load(self, stream: TextIO) -> YamlNode: ...
    def dump(self, data: object, stream: TextIO) -> None: ...
