"""Apply query and filter rules to parsed papers."""

from confer_parse_dub.models.config import Config
from confer_parse_dub.models.paper import Affiliation, ParsedPaper


def apply_filters(config: Config, papers: list[ParsedPaper]) -> list[ParsedPaper]:
    """
    Filter papers according to the config rules.

    Order of precedence (highest first):
      1. include_paper       — always included, overrides everything
      2. exclude_paper       — always excluded, overrides query and institution rules
      3. query               — paper must match at least one query rule
                               (keywords checked against institution AND dsl)
      4. exclude_institution — excluded if every keyword-matching affiliation's
      4. exclude_dsl           institution or dsl is covered by an exclusion rule
    """
    include_ids = {r.id for r in config.include_paper}
    exclude_ids = {r.id for r in config.exclude_paper}
    exclude_inst = {r.name.casefold() for r in config.exclude_institution}
    exclude_dsl = {r.name.casefold() for r in config.exclude_dsl}
    all_keywords = [kw for rule in config.query for kw in rule.keywords]

    result = []
    for paper in papers:
        if paper.id in include_ids:
            result.append(paper)
            continue

        if paper.id in exclude_ids:
            continue

        if not _matches_query(config, paper):
            continue

        if (exclude_inst or exclude_dsl) and _all_matching_affiliations_excluded(
            paper, all_keywords, exclude_inst, exclude_dsl
        ):
            continue

        result.append(paper)

    return result


def _matches_query(config: Config, paper: ParsedPaper) -> bool:
    """Return True if the paper matches at least one query rule."""
    for rule in config.query:
        if rule.tracks and paper.trackId not in {t.id for t in rule.tracks}:
            continue

        if rule.keywords:
            matched = any(
                _keyword_matches_affiliation(kw, affil)
                for author in paper.authors
                for affil in author.affiliations
                for kw in rule.keywords
            )
            if not matched:
                continue

        return True

    return False


def _keyword_matches_affiliation(keyword: str, affil: Affiliation) -> bool:
    """Return True if the keyword appears in the affiliation's institution or dsl."""
    kw = keyword.casefold()
    return kw in affil.institution.casefold() or kw in affil.dsl.casefold()


def _all_matching_affiliations_excluded(
    paper: ParsedPaper,
    keywords: list[str],
    excluded_institutions: set[str],
    excluded_dsls: set[str],
) -> bool:
    """
    Return True if every keyword-matching affiliation for this paper is covered
    by either an excluded institution or an excluded DSL.

    A paper with at least one matching affiliation not covered by any exclusion
    rule is kept.
    """
    casefold_keywords = [k.casefold() for k in keywords]
    matching = [
        affil
        for author in paper.authors
        for affil in author.affiliations
        if any(
            kw in affil.institution.casefold() or kw in affil.dsl.casefold()
            for kw in casefold_keywords
        )
    ]
    if not matching:
        return False

    for affil in matching:
        inst_matched = bool(affil.institution) and any(
            kw in affil.institution.casefold() for kw in casefold_keywords
        )
        dsl_matched = bool(affil.dsl) and any(
            kw in affil.dsl.casefold() for kw in casefold_keywords
        )

        inst_passes = (
            inst_matched and affil.institution.casefold() not in excluded_institutions
        )
        dsl_passes = dsl_matched and affil.dsl.casefold() not in excluded_dsls

        if inst_passes or dsl_passes:
            return False  # At least one path is open — paper is not excluded.

    return True
