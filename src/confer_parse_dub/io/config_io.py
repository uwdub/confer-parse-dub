"""Pure YAML ↔ Pydantic transformation for conference config files."""

import pathlib
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from confer_parse_dub.models.config import (
    AffiliationEntry,
    AffiliationMatchRule,
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
    """Return the EOL comment on the first key of a ruamel CommentedMap."""
    if not hasattr(item, "ca") or not hasattr(item, "keys"):
        return None
    first_key = next(iter(item), None)
    if first_key is None:
        return None
    tokens = item.ca.items.get(first_key)
    if not tokens or tokens[2] is None:
        return None
    return tokens[2].value.strip().lstrip("#").strip() or None



def _attach_comment(item: CommentedMap, model: CommentedModel) -> CommentedMap:
    """Attach model.comment as an EOL comment on the first key of item."""
    if model.comment and item:
        item.yaml_add_eol_comment(model.comment, key=next(iter(item)))
    return item


def _to_commented_item(model: CommentedModel) -> CommentedMap:
    """Convert a flat CommentedModel to a CommentedMap with its comment attached."""
    return _attach_comment(CommentedMap(model.model_dump(exclude_none=True)), model)



def _affiliations_to_seq(entries: list[AffiliationEntry]) -> CommentedSeq:
    """Convert a sorted list of AffiliationEntry models to a CommentedSeq."""
    seq = CommentedSeq()
    for entry in sorted(entries, key=lambda e: e.canonical):
        aff_item = CommentedMap({"canonical": entry.canonical})
        if entry.match:

            def _match_sort_key(r: AffiliationMatchRule) -> tuple[str, str]:
                first = r.affiliations[0] if r.affiliations else None
                return (
                    first.institution or "" if first else "",
                    first.dsl or "" if first else "",
                )

            aff_item["match"] = CommentedSeq(
                [
                    _attach_comment(CommentedMap(r.model_dump(exclude_none=True)), r)
                    for r in sorted(entry.match, key=_match_sort_key)
                ]
            )
        if entry.reject:
            aff_item["reject"] = CommentedSeq(
                [_to_commented_item(r) for r in entry.reject]
            )
        _attach_comment(aff_item, entry)
        seq.append(aff_item)
    return seq


def _config_to_doc(config: Config) -> CommentedMap:
    """
    Convert a Config model to a ruamel.yaml CommentedMap ready for serialization.
    All lists are sorted.  Comments stored in model fields are written as inline
    YAML comments.
    """
    doc = CommentedMap()
    doc["version"] = config.version
    doc["file_input"] = config.file_input
    doc["file_output"] = config.file_output

    # query — sorted by first keyword then first track id
    query_seq = CommentedSeq()
    for rule in sorted(
        config.query,
        key=lambda r: (sorted(r.keywords)[:1], sorted(t.id for t in r.tracks)[:1]),
    ):
        item = CommentedMap()
        item["keywords"] = CommentedSeq(sorted(rule.keywords))
        item["tracks"] = CommentedSeq(
            [_to_commented_item(t) for t in sorted(rule.tracks, key=lambda t: t.id)]
        )
        _attach_comment(item, rule)
        query_seq.append(item)
    doc["query"] = query_seq

    # institution / dsl include+exclude — sorted by name
    for attr in (
        "include_institution",
        "exclude_institution",
        "include_dsl",
        "exclude_dsl",
    ):
        doc[attr] = CommentedSeq(
            [
                _to_commented_item(r)
                for r in sorted(getattr(config, attr), key=lambda r: r.name)
            ]
        )

    # include_paper / exclude_paper — sorted by id
    for attr in ("include_paper", "exclude_paper"):
        doc[attr] = CommentedSeq(
            [
                _to_commented_item(r)
                for r in sorted(getattr(config, attr), key=lambda r: r.id)
            ]
        )

    # names — sorted by name
    names_seq = CommentedSeq()
    for entry in sorted(config.names, key=lambda e: e.name):
        name_item = CommentedMap({"name": entry.name})
        if entry.match:
            name_item["match"] = CommentedSeq(
                [_to_commented_item(m) for m in entry.match]
            )
        _attach_comment(name_item, entry)
        names_seq.append(name_item)
    doc["names"] = names_seq

    # internal_affiliations / external_affiliations — sorted by canonical
    doc["internal_affiliations"] = _affiliations_to_seq(config.internal_affiliations)
    doc["external_affiliations"] = _affiliations_to_seq(config.external_affiliations)

    return doc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(path: pathlib.Path) -> Config:
    """
    Read config.yml, extract inline YAML comments into model fields, and
    return a fully validated Config.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = _yaml.load(f)

    plain: dict[str, Any] = _to_plain(raw) if raw else {}

    # Inject comments for all list sections whose items are CommentedModel subclasses.
    for section in (
        "query",
        "include_institution",
        "exclude_institution",
        "include_dsl",
        "exclude_dsl",
        "include_paper",
        "exclude_paper",
        "names",
        "internal_affiliations",
        "external_affiliations",
    ):
        for i, item in enumerate((raw or {}).get(section, [])):
            comment = _first_key_comment(item)
            if comment:
                plain.setdefault(section, [])[i]["comment"] = comment

    return Config.model_validate(plain)


def save_config(path: pathlib.Path, config: Config) -> None:
    """Serialize config to disk, writing model comments as inline YAML comments."""
    with open(path, "w", encoding="utf-8") as f:
        _yaml.dump(_config_to_doc(config), f)
