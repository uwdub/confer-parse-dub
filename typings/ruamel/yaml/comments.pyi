from __future__ import annotations

class _CommentToken:
    value: str

class _CommentAttrib:
    items: dict[
        object,
        tuple[
            object | None,
            object | None,
            _CommentToken | None,
            object | None,
        ],
    ]

class CommentedMap(dict[str, object]):
    ca: _CommentAttrib

    def yaml_add_eol_comment(self, comment: str, key: str | None = None) -> None: ...

class CommentedSeq(list[object]): ...
