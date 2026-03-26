"""Pure YAML ↔ Pydantic transformation for conference config files."""

import pathlib
from typing import Any, get_origin

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from confer_parse_dub.models.config import (
    CommentedModel,
    Config,
)

# A single YAML instance is reused for all IO in this module.
_yaml = YAML()
_yaml.preserve_quotes = True


# ---------------------------------------------------------------------------
# YAML ↔ Pydantic conversion helpers
# ---------------------------------------------------------------------------


def _to_plain(obj: Any) -> Any:
    """Recursively convert ruamel.yaml objects to plain Python dicts/lists."""
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_plain(item) for item in obj]
    else:
        return obj


def _first_key_comment(item: Any) -> str | None:
    """Return the first EOL comment found on any key of a ruamel CommentedMap."""
    if not hasattr(item, "ca") or not hasattr(item, "keys"):
        return None
    for key in item:
        tokens = item.ca.items.get(key)
        if tokens and tokens[2] is not None:
            return tokens[2].value.strip().lstrip("#").strip() or None
    return None


def _attach_comment(item: CommentedMap, model: CommentedModel) -> CommentedMap:
    """Attach model.comment as an EOL comment on the first key of item."""
    if model.comment and item:
        item.yaml_add_eol_comment(model.comment, key=next(iter(item)))
    return item


def _to_yaml_value(value: Any) -> Any:
    """Recursively convert a model value to ruamel-yaml structure."""
    if isinstance(value, CommentedModel):
        return _model_to_map(value)
    if isinstance(value, list):
        return _list_to_seq(value)
    return value


def _list_to_seq(items: list[Any]) -> CommentedSeq:
    """Convert a list to a CommentedSeq, sorting CommentedModel items by sort_key()
    and plain strings alphabetically."""
    if not items:
        return CommentedSeq()
    if isinstance(items[0], CommentedModel):
        return CommentedSeq(
            [_model_to_map(item) for item in sorted(items, key=lambda x: x.sort_key())]
        )
    if isinstance(items[0], str):
        return CommentedSeq(sorted(items))
    return CommentedSeq(items)


def _model_to_map(model: CommentedModel) -> CommentedMap:
    """Convert any CommentedModel to a CommentedMap, skipping None and empty lists."""
    result = CommentedMap()
    for field_name in type(model).model_fields:
        if field_name == "comment":
            continue
        value = getattr(model, field_name)
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        result[field_name] = _to_yaml_value(value)
    _attach_comment(result, model)
    return result


def _config_to_doc(config: Config) -> CommentedMap:
    doc = CommentedMap()
    for field_name in Config.model_fields:
        value = getattr(config, field_name)
        doc[field_name] = _list_to_seq(value) if isinstance(value, list) else value
    return doc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _inject_comments(raw_obj: Any, plain_obj: Any) -> None:
    """Recursively walk raw ruamel YAML and inject comments into the plain dict/list."""
    if isinstance(raw_obj, list) and isinstance(plain_obj, list):
        for raw_item, plain_item in zip(raw_obj, plain_obj):
            if isinstance(raw_item, dict) and isinstance(plain_item, dict):
                comment = _first_key_comment(raw_item)
                if comment:
                    plain_item["comment"] = comment
                # Recurse into nested dict values
                for key in raw_item:
                    if key in plain_item:
                        _inject_comments(raw_item[key], plain_item[key])
    elif isinstance(raw_obj, dict) and isinstance(plain_obj, dict):
        for key in raw_obj:
            if key in plain_obj:
                _inject_comments(raw_obj[key], plain_obj[key])


def load_config(path: pathlib.Path) -> Config:
    """
    Read config.yml, extract inline YAML comments into model fields, and
    return a fully validated Config.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = _yaml.load(f)

    plain: dict[str, Any] = _to_plain(raw) if raw else {}

    for field_name, field_info in Config.model_fields.items():
        if get_origin(field_info.annotation) is list:
            for i, item in enumerate((raw or {}).get(field_name, [])):
                comment = _first_key_comment(item)
                if comment:
                    plain.setdefault(field_name, [])[i]["comment"] = comment
                # Recurse into nested lists within this item
                if isinstance(item, dict) and isinstance(plain.get(field_name, [None] * (i + 1))[i], dict):
                    plain_item = plain[field_name][i]
                    for sub_key in item:
                        if sub_key in plain_item:
                            _inject_comments(item[sub_key], plain_item[sub_key])

    return Config.model_validate(plain)


def save_config(path: pathlib.Path, config: Config) -> None:
    """Serialize config to disk, writing model comments as inline YAML comments."""
    with open(path, "w", encoding="utf-8") as f:
        _yaml.dump(_config_to_doc(config), f)
