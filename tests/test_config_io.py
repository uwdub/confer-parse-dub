"""Tests for config_io load/save round-trip and comment handling."""

import pathlib

from confer_parse_dub.io.config_io import load_config, save_config

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
SAMPLE_CONFIG = FIXTURES_DIR / "sample_config.yml"


def test_load_produces_correct_model() -> None:
    config = load_config(SAMPLE_CONFIG)

    assert config.version == "v1"
    assert config.file_input == "program.json"
    assert config.file_output == "papers.csv"

    # Two query rules
    assert len(config.query) == 2

    # include_institution has MIT and Stanford entries
    institution_names = {r.name for r in config.include_institution}
    assert "MIT" in institution_names
    assert "Stanford University" in institution_names

    # One exclude_paper with id=42
    assert len(config.exclude_paper) == 1
    assert config.exclude_paper[0].id == 42

    # Two name entries
    assert len(config.names) == 2
    jane = next(e for e in config.names if e.name == "Jane Smith")
    assert len(jane.match) == 2

    # internal_affiliations has MIT with a match rule and a reject rule
    mit = next(
        e
        for e in config.internal_affiliations
        if e.canonical == "Massachusetts Institute of Technology"
    )
    assert len(mit.match) == 1
    assert len(mit.reject) == 1

    # external_affiliations has Google with a match rule that has name and affiliations
    google = next(e for e in config.external_affiliations if e.canonical == "Google")
    assert len(google.match) == 1
    assert google.match[0].name == "John Doe"
    assert len(google.match[0].affiliations) == 1


def test_comments_are_loaded() -> None:
    config = load_config(SAMPLE_CONFIG)

    # MIT in include_institution has comment "Cambridge"
    mit = next(r for r in config.include_institution if r.name == "MIT")
    assert mit.comment == "Cambridge"

    # Jane Smith in names has comment "canonical"
    jane = next(e for e in config.names if e.name == "Jane Smith")
    assert jane.comment == "canonical"

    # MIT in internal_affiliations has comment "MIT"
    mit_aff = next(
        e
        for e in config.internal_affiliations
        if e.canonical == "Massachusetts Institute of Technology"
    )
    assert mit_aff.comment == "MIT"

    # exclude_paper entry with id=42 has comment "demo paper"
    paper = next(p for p in config.exclude_paper if p.id == 42)
    assert paper.comment == "demo paper"

    # Papers TrackRule in the first query rule has comment "main track"
    first_query = next(r for r in config.query if "hci" in r.keywords)
    papers_track = next(t for t in first_query.tracks if t.name == "Papers")
    assert papers_track.comment == "main track"


def test_round_trip(tmp_path: pathlib.Path) -> None:
    config = load_config(SAMPLE_CONFIG)
    out = tmp_path / "config.yml"
    save_config(out, config)
    reloaded = load_config(out)

    assert reloaded.version == config.version
    assert reloaded.file_input == config.file_input
    assert reloaded.file_output == config.file_output

    assert len(reloaded.query) == len(config.query)
    assert len(reloaded.include_institution) == len(config.include_institution)
    assert len(reloaded.exclude_institution) == len(config.exclude_institution)
    assert len(reloaded.include_dsl) == len(config.include_dsl)
    assert len(reloaded.exclude_dsl) == len(config.exclude_dsl)
    assert len(reloaded.include_paper) == len(config.include_paper)
    assert len(reloaded.exclude_paper) == len(config.exclude_paper)
    assert len(reloaded.names) == len(config.names)
    assert len(reloaded.internal_affiliations) == len(config.internal_affiliations)
    assert len(reloaded.external_affiliations) == len(config.external_affiliations)

    # Spot-check a few values
    assert reloaded.exclude_paper[0].id == 42
    jane = next(e for e in reloaded.names if e.name == "Jane Smith")
    assert len(jane.match) == 2

    mit = next(
        e
        for e in reloaded.internal_affiliations
        if e.canonical == "Massachusetts Institute of Technology"
    )
    assert len(mit.match) == 1
    assert len(mit.reject) == 1


def test_comments_survive_round_trip(tmp_path: pathlib.Path) -> None:
    config = load_config(SAMPLE_CONFIG)
    out = tmp_path / "config.yml"
    save_config(out, config)
    reloaded = load_config(out)

    mit = next(r for r in reloaded.include_institution if r.name == "MIT")
    assert mit.comment == "Cambridge"

    jane = next(e for e in reloaded.names if e.name == "Jane Smith")
    assert jane.comment == "canonical"

    mit_aff = next(
        e
        for e in reloaded.internal_affiliations
        if e.canonical == "Massachusetts Institute of Technology"
    )
    assert mit_aff.comment == "MIT"

    paper = next(p for p in reloaded.exclude_paper if p.id == 42)
    assert paper.comment == "demo paper"

    first_query = next(r for r in reloaded.query if "hci" in r.keywords)
    papers_track = next(t for t in first_query.tracks if t.name == "Papers")
    assert papers_track.comment == "main track"


def test_save_sorts_items(tmp_path: pathlib.Path) -> None:
    config = load_config(SAMPLE_CONFIG)
    out = tmp_path / "config.yml"
    save_config(out, config)
    reloaded = load_config(out)

    # In include_institution: MIT comes before Stanford in saved output
    institution_names = [r.name for r in reloaded.include_institution]
    assert institution_names.index("MIT") < institution_names.index(
        "Stanford University"
    )

    # In names: Jane Smith comes before John Doe in saved output
    name_list = [e.name for e in reloaded.names]
    assert name_list.index("Jane Smith") < name_list.index("John Doe")

    # In first query rule tracks: id 200 comes before 201 in saved output
    first_query = next(r for r in reloaded.query if "hci" in r.keywords)
    track_ids = [t.id for t in first_query.tracks]
    assert track_ids.index(200) < track_ids.index(201)
