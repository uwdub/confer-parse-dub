"""Invoke tasks for this project."""

from invoke.collection import Collection

import confer_parse_dub.tasks.conference
import confer_parse_dub.tasks.format
import confer_parse_dub.tasks.lint
import confer_parse_dub.tasks.test
from confer_parse_dub.io.conferences_io import load_conferences

# Root namespace for tasks.
namespace: Collection = Collection()

# Conference management hub (always present).
namespace.add_task(confer_parse_dub.tasks.conference.get_task_conferences())

# One subcollection per active conference (e.g., invoke chi2025, invoke chi2025.fetch).
# Completed conferences are omitted — use 'invoke run --config ...' for those.
_conferences = load_conferences()
for _conf in _conferences:
    if not _conf.complete:
        namespace.add_collection(
            confer_parse_dub.tasks.conference.get_collection_for_conference(_conf)
        )

# Development tasks.
namespace.add_task(confer_parse_dub.tasks.format.get_task_format())
namespace.add_task(confer_parse_dub.tasks.lint.get_task_lint())
namespace.add_task(confer_parse_dub.tasks.test.get_task_test())
