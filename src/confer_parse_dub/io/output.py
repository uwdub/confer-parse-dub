"""Write processed papers to a YAML output file."""

import pathlib
from typing import Any

from ruamel.yaml import YAML

from confer_parse_dub.models.paper import ParsedPaper
from confer_parse_dub.models.state import ProcessingState


def check_resolved(papers: list[ParsedPaper], state: ProcessingState) -> list[str]:
    """
    Return a list of problem descriptions if output cannot be generated.

    An empty list means all items are resolved and output is ready.

    Only skipped names block output: we cannot write a paper when an
    author's name is still unresolved.  Unresolved or skipped affiliations
    are written as empty strings and do not block output — a paper is
    included because *at least one* author matched, and co-authors whose
    affiliations were not normalised should not prevent the paper from
    appearing.
    """
    problems = []

    for paper in papers:
        for author in paper.authors:
            if author.name in state.skipped_names:
                problems.append(
                    "Skipped name: '{}' in paper {}".format(author.name, paper.id)
                )

    return problems


def write_output(papers: list[ParsedPaper], path: pathlib.Path) -> None:
    """Write papers to YAML output file."""
    papers_data = [_paper_to_dict(p) for p in papers]

    yaml = YAML()
    yaml.default_flow_style = False

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump({"papers": papers_data}, f)


def _paper_to_dict(paper: ParsedPaper) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": paper.id,
        "title": paper.title,
        "bestpaper": paper.bestpaper,
        "honorablemention": paper.honorablemention,
        "authors": [
            {
                "name": author.name,
                "affiliation": " / ".join(author.canonical_affiliations),
            }
            for author in paper.authors
        ],
        "trackId": paper.trackId,
        "typeId": paper.typeId,
        "sessionIds": paper.sessionIds,
        "source": paper.source,
        "eventIds": paper.eventIds,
        "recognitionIds": paper.recognitionIds,
        "importedId": paper.importedId,
        "isBreak": paper.isBreak,
    }
    if paper.doi:
        data["doi"] = paper.doi
    return data
