"""Pure YAML ↔ Pydantic transformation for conference config files."""

import pathlib
from typing import cast, get_origin

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from confer_parse_dub.models.config import (
    CommentedModel,
    Config,
)

# A single YAML instance is reused for all IO in this module.
_yaml = YAML()
_yaml.preserve_quotes = True

PlainValue = object
PlainMap = dict[str, PlainValue]


# ---------------------------------------------------------------------------
# YAML ↔ Pydantic conversion helpers
# ---------------------------------------------------------------------------


def _to_plain(obj: object) -> object:
    """Recursively convert ruamel.yaml objects to plain Python dicts/lists."""
    if isinstance(obj, dict):
        obj_dict = cast(dict[object, object], obj)
        return {str(k): _to_plain(v) for k, v in obj_dict.items()}
    elif isinstance(obj, list):
        obj_list = cast(list[object], obj)
        return [_to_plain(item) for item in obj_list]
    else:
        return obj


def _first_key_comment(item: object) -> str | None:
    """Return the first EOL comment found on any key of a ruamel CommentedMap."""
    if not isinstance(item, CommentedMap):
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


def _to_yaml_value(value: object) -> object:
    """Recursively convert a model value to ruamel-yaml structure."""
    if isinstance(value, CommentedModel):
        return _model_to_map(value)
    if isinstance(value, list):
        return _list_to_seq(cast(list[object], value))
    return value


def _list_to_seq(items: list[object]) -> CommentedSeq:
    """Convert a list to a CommentedSeq, sorting CommentedModel items by sort_key()
    and plain strings alphabetically."""
    if not items:
        return CommentedSeq()
    if isinstance(items[0], CommentedModel):
        model_items = [item for item in items if isinstance(item, CommentedModel)]
        return CommentedSeq(
            [
                _model_to_map(item)
                for item in sorted(model_items, key=lambda model: str(model.sort_key()))
            ]
        )
    if isinstance(items[0], str):
        str_items = [item for item in items if isinstance(item, str)]
        return CommentedSeq(sorted(str_items))
    return CommentedSeq(items)


def _model_to_map(model: CommentedModel) -> CommentedMap:
    """Convert any CommentedModel to a CommentedMap, skipping None and empty lists."""
    result = CommentedMap()
    for field_name in type(model).model_fields:
        if field_name == "comment":
            continue
        value: object = cast(object, getattr(model, field_name))
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        yaml_value = _to_yaml_value(cast(object, value))
        result[field_name] = yaml_value
    _ = _attach_comment(result, model)
    return result


def _config_to_doc(config: Config) -> CommentedMap:
    doc = CommentedMap()
    for field_name in Config.model_fields:
        value: object = cast(object, getattr(config, field_name))
        doc[field_name] = (
            _list_to_seq(cast(list[object], value))
            if isinstance(value, list)
            else value
        )
    return doc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _inject_comments(raw_obj: object, plain_obj: object) -> None:
    """Recursively walk raw ruamel YAML and inject comments into the plain dict/list."""
    if isinstance(raw_obj, list) and isinstance(plain_obj, list):
        raw_list = cast(list[object], raw_obj)
        plain_list = cast(list[object], plain_obj)
        for raw_item, plain_item in zip(raw_list, plain_list):
            if isinstance(raw_item, dict) and isinstance(plain_item, dict):
                raw_item_dict = cast(dict[object, object], raw_item)
                plain_item_dict = cast(dict[str, object], plain_item)
                comment = _first_key_comment(cast(object, raw_item))
                if comment:
                    plain_item_dict["comment"] = comment
                # Recurse into nested dict values
                for key in raw_item_dict:
                    if isinstance(key, str) and key in plain_item_dict:
                        _inject_comments(raw_item_dict[key], plain_item_dict[key])
    elif isinstance(raw_obj, dict) and isinstance(plain_obj, dict):
        raw_dict = cast(dict[object, object], raw_obj)
        plain_dict = cast(dict[str, object], plain_obj)
        for key in raw_dict:
            if isinstance(key, str) and key in plain_dict:
                _inject_comments(raw_dict[key], plain_dict[key])


def load_config(path: pathlib.Path) -> Config:
    """
    Read config.yml, extract inline YAML comments into model fields, and
    return a fully validated Config.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = _yaml.load(f)

    plain_raw: object = _to_plain(raw) if raw else {}
    plain: PlainMap = cast(PlainMap, plain_raw) if isinstance(plain_raw, dict) else {}
    raw_map: CommentedMap = raw if isinstance(raw, CommentedMap) else CommentedMap()

    for field_name, field_info in Config.model_fields.items():
        if get_origin(field_info.annotation) is list:
            raw_items_obj: object = raw_map.get(field_name, [])
            raw_items: list[object] = (
                cast(list[object], raw_items_obj)
                if isinstance(raw_items_obj, list)
                else []
            )
            for i, item in enumerate(raw_items):
                comment = _first_key_comment(item)
                plain_field_obj = plain.get(field_name)
                plain_field = (
                    cast(list[object], plain_field_obj)
                    if isinstance(plain_field_obj, list)
                    else None
                )
                if not isinstance(plain_field, list) or i >= len(plain_field):
                    continue
                plain_item_obj = plain_field[i]
                if not isinstance(plain_item_obj, dict):
                    continue
                plain_item = cast(dict[str, object], plain_item_obj)
                if comment:
                    plain_item["comment"] = comment
                # Recurse into nested lists within this item
                if isinstance(item, dict):
                    item_dict = cast(dict[object, object], item)
                    for sub_key in item_dict:
                        if isinstance(sub_key, str) and sub_key in plain_item:
                            _inject_comments(item_dict[sub_key], plain_item[sub_key])

    return Config.model_validate(plain)


def save_config(path: pathlib.Path, config: Config) -> None:
    """Serialize config to disk, writing model comments as inline YAML comments."""
    with open(path, "w", encoding="utf-8") as f:
        _ = _yaml.dump(_config_to_doc(config), f)
