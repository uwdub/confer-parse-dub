"""Parse raw SIGCHI program JSON into structured paper data."""

import json

from confer_parse_dub.models.config import Config
from confer_parse_dub.models.paper import Affiliation, ParsedAuthor, ParsedPaper
from confer_parse_dub.models.program import (
    RawContentInput,
    RawPersonInput,
    RawProgramInput,
)
from confer_parse_dub.processing.normalize_text import normalize_text


def _load_program(config: Config) -> RawProgramInput:
    with open(config.file_input, "r", encoding="utf-8") as f:
        return RawProgramInput.model_validate(json.load(f))


def parse_tracks(config: Config) -> dict[int, str]:
    """Return {trackId: trackName} from the raw JSON tracks list."""
    program = _load_program(config)
    return {t.id: t.name or "(unnamed)" for t in program.tracks}


def count_papers_by_track(config: Config) -> dict[int, int]:
    """Return {trackId: item_count} from raw JSON contents."""
    program = _load_program(config)
    counts: dict[int, int] = {}
    for content in program.contents:
        if content.trackId is not None:
            counts[content.trackId] = counts.get(content.trackId, 0) + 1
    return counts


def parse_sigchi_program(config: Config) -> list[ParsedPaper]:
    """Parse a SIGCHI program JSON file into a list of ParsedPapers."""
    program = _load_program(config)
    people_by_id = {person.id: person for person in program.people}
    tracks = {t.id: t.name or "(unnamed)" for t in program.tracks}

    papers: list[ParsedPaper] = []
    for content in program.contents:
        paper = _parse_content(content, people_by_id, tracks)
        if paper is not None:
            papers.append(paper)

    return papers


def _parse_content(
    content: RawContentInput,
    people_by_id: dict[int, RawPersonInput],
    tracks: dict[int, str],
) -> ParsedPaper | None:
    """Parse a single content item into a ParsedPaper."""
    # Extract award flags.
    bestpaper = content.award == "BEST_PAPER"
    honorablemention = content.award == "HONORABLE_MENTION"

    # Extract supported paper links from content.addons.
    doi: str | None = None
    for addon in content.addons.values():
        if not addon.url:
            continue
        if addon.type == "doiLink":
            doi = addon.url

    # Expand authors from personId.
    authors: list[ParsedAuthor] = []
    for raw_author in content.authors:
        person = people_by_id.get(raw_author.personId)
        if person is None:
            continue

        name_parts: list[str] = []
        if person.firstName:
            name_parts.append(person.firstName)
        middle = person.middleInitial.strip(".")
        if middle:
            name_parts.extend(middle.split("."))
        if person.lastName:
            name_parts.append(person.lastName)
        name = normalize_text(" ".join(name_parts))

        affiliations = [
            Affiliation(
                institution=normalize_text(a.institution),
                dsl=normalize_text(a.dsl),
                city=a.city,
                state=a.state,
                country=a.country,
            )
            for a in raw_author.affiliations
        ]

        authors.append(ParsedAuthor(name=name, affiliations=affiliations))

    return ParsedPaper(
        id=content.id,
        title=normalize_text(content.title),
        trackId=content.trackId,
        track_name=tracks.get(content.trackId) if content.trackId is not None else None,
        typeId=content.typeId,
        sessionIds=content.sessionIds,
        eventIds=content.eventIds,
        recognitionIds=content.recognitionIds,
        importedId=content.importedId,
        source=content.source,
        isBreak=content.isBreak,
        doi=doi,
        bestpaper=bestpaper,
        honorablemention=honorablemention,
        authors=authors,
    )
