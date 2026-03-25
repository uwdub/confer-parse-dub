"""Apply title-case normalization to paper titles."""

import titlecase

from confer_parse_dub.models.paper import ParsedPaper
from confer_parse_dub.processing.normalize_text import normalize_text


def normalize_titles(papers: list[ParsedPaper]) -> list[ParsedPaper]:
    """Apply title-case normalization to all paper titles."""
    for paper in papers:
        paper.title = _normalize_title(paper.title)

    return papers


def _normalize_title(title: str) -> str:
    title = normalize_text(title)
    title = titlecase.titlecase(title)

    # Fix specific phrases titlecase handles incorrectly.
    title = title.replace("in Situ", "In Situ")
    title = title.replace("Human-Ai", "Human-AI")

    return title
