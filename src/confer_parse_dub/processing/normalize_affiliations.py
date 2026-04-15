"""Author affiliation normalization — lookup only."""

from confer_parse_dub.models.config import AffiliationEntry, Config
from confer_parse_dub.models.paper import Affiliation


def affiliation_key(author_name: str, affiliations: list[Affiliation]) -> str:
    """Compute a unique state key for an (author, affiliations) pair."""
    parts = sorted("{}/{}".format(a.institution, a.dsl) for a in affiliations)
    return "{}::{}".format(author_name, "|".join(parts))


def find_all_matching_affiliations(
    config: Config,
    author_name: str,
    affiliations: list[Affiliation],
) -> list[AffiliationEntry]:
    """
    Return all canonical affiliation entries that match for this (author, affiliations) pair.

    Searches both internal_affiliations and external_affiliations.  Each entry
    is included at most once.  Reject rules are applied before returning.

    A well-formed config produces at most one result for any input.  The caller
    is responsible for detecting and reporting multiple matches.

    Shortcut: if the author has exactly one affiliation whose institution
    exactly equals a canonical, that canonical matches unconditionally.
    """
    all_entries = config.internal_affiliations + config.external_affiliations
    matches_found: list[AffiliationEntry] = []

    for affil_entry in all_entries:
        # Shortcut checked unconditionally — explicit match rules do not disable it.
        if (
            len(affiliations) == 1
            and affiliations[0].institution == affil_entry.canonical
            and affil_entry not in matches_found
        ):
            matches_found.append(affil_entry)
            continue

        for match_rule in affil_entry.match + affil_entry.match_for_name:
            match_current = True

            if match_rule.name is not None:
                match_current = match_current and match_rule.name == author_name

            if match_rule.affiliations:
                matched_patterns = 0
                for pattern in match_rule.affiliations:
                    for affil in affiliations:
                        affil_match = True
                        if pattern.institution is not None:
                            affil_match = (
                                affil_match and pattern.institution == affil.institution
                            )
                        if pattern.dsl is not None:
                            affil_match = affil_match and pattern.dsl == affil.dsl
                        if affil_match:
                            matched_patterns += 1
                            break

                match_current = match_current and (
                    matched_patterns == len(match_rule.affiliations)
                )

            if match_current and affil_entry not in matches_found:
                matches_found.append(affil_entry)

    # Apply reject rules.
    return [
        m
        for m in matches_found
        if not any(r.name is not None and r.name == author_name for r in m.reject)
    ]


def is_internal_affiliation(config: Config, affiliations: list[Affiliation]) -> bool:
    """
    Return True if any affiliation institution matches an include_institution rule.

    This mirrors the affiliation-review classification: institutions accepted
    during ReviewAffiliationsStep land in include_institution, so a match here
    means the affiliation is at our institution.  Everything else is external.
    """
    included = {r.name.casefold() for r in config.include_institution}
    return any(
        a.institution and a.institution.casefold() in included for a in affiliations
    )


def find_canonical_affiliation(
    config: Config,
    author_name: str,
    affiliations: list[Affiliation],
) -> str | None:
    """
    Return the canonical affiliation for an author, or None if unresolved.

    Returns None both when no entry matches and when more than one matches.
    The config validator ensures at most one entry matches any input, so
    multiple matches indicate a config error that should have been caught earlier.
    """
    matches = find_all_matching_affiliations(config, author_name, affiliations)
    if len(matches) == 1:
        return matches[0].canonical
    return None
