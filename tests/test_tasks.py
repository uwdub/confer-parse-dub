"""Tests for task registration."""

from collections.abc import Iterable
from typing import cast

from invoke.collection import Collection


def test_namespace_has_required_tasks() -> None:
    """
    Importing tasks must succeed and the root namespace must expose core tasks.

    Catches syntax errors, bad imports, broken conference registry reads, and
    anything else that would make 'invoke -l' unusable.
    """
    import tasks

    assert isinstance(tasks.namespace, Collection)

    task_names = set[str](tasks.namespace.task_names.keys())
    assert "conferences" in task_names
    assert "format" in task_names
    assert "lint" in task_names
    assert "test" in task_names


def test_active_conferences_registered() -> None:
    """Each active conference in conferences.yml must appear as a task collection."""
    import tasks
    from confer_parse_dub.io.conferences_io import load_conferences

    conferences = load_conferences()
    active = [c for c in conferences if not c.complete]

    collections = set[str](
        cast(Iterable[str], tasks.namespace.collections.keys()),
    )
    for conf in active:
        assert conf.name in collections, (
            "Active conference '{}' not found as a task collection".format(conf.name)
        )
