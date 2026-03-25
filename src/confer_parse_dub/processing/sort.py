"""Sort processed papers."""

import string

from confer_parse_dub.models.paper import ParsedPaper


def sort_papers(papers: list[ParsedPaper]) -> list[ParsedPaper]:
    """Sort papers by award status (best paper first), then alphabetically by title."""
    papers = sorted(papers, key=lambda p: _title_sort_key(p.title))
    papers = sorted(papers, key=lambda p: p.honorablemention, reverse=True)
    papers = sorted(papers, key=lambda p: p.bestpaper, reverse=True)
    return papers


def _title_sort_key(title: str) -> str:
    return "".join(
        c for c in title if c in string.ascii_letters + string.digits
    ).casefold()
