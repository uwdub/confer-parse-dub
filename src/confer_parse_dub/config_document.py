"""Stateful wrapper around a conference config file with mutation methods."""

import pathlib
from collections.abc import Callable
from typing import TYPE_CHECKING

from confer_parse_dub.exceptions import ConfigError
from confer_parse_dub.io.config_io import load_config, save_config
from confer_parse_dub.models.config import (
    AffiliationEntry,
    AffiliationMatchRule,
    Config,
    DslRule,
    InstitutionRule,
    ManualSplitRule,
    NameEntry,
    NameMatch,
    PaperRule,
    QueryRule,
)
from confer_parse_dub.processing.normalize_affiliations import (
    affiliation_key,
    find_all_matching_affiliations,
)

if TYPE_CHECKING:
    from confer_parse_dub.models.paper import ParsedPaper


# ---------------------------------------------------------------------------
# Invariant validation
# ---------------------------------------------------------------------------


def _check_unique_strs(list_name: str, values: list[str]) -> None:
    seen: set[str] = set()
    for v in values:
        if v in seen:
            raise ConfigError(f"Duplicate entry in {list_name}: {v!r}")
        seen.add(v)


def _check_unique_ints(list_name: str, values: list[int]) -> None:
    seen: set[int] = set()
    for v in values:
        if v in seen:
            raise ConfigError(f"Duplicate entry in {list_name}: {v}")
        seen.add(v)


def _check_disjoint_strs(
    list_a: str, set_a: set[str], list_b: str, set_b: set[str]
) -> None:
    overlap = set_a & set_b
    if overlap:
        example = next(iter(sorted(overlap)))
        raise ConfigError(f"Entry appears in both {list_a} and {list_b}: {example!r}")


def _check_disjoint_ints(
    list_a: str, set_a: set[int], list_b: str, set_b: set[int]
) -> None:
    overlap = set_a & set_b
    if overlap:
        example = next(iter(sorted(overlap)))
        raise ConfigError(f"Entry appears in both {list_a} and {list_b}: {example}")


def validate_config(config: Config, papers: "list[ParsedPaper] | None" = None) -> None:
    """
    Raise ConfigError if any config invariant is violated.

    Called at three points:
      1. Load time — config file just read, no papers yet (structural checks only).
      2. After papers are loaded — config validated against the actual data before
         any mutations begin.
      3. After every mutation — via apply(), with papers when available.
    """
    # --- names ---
    # Every name value (canonical or alias) must be globally unique.
    # This ensures exactly one canonical matches any raw author name.
    all_name_values: dict[str, str] = {}  # value -> description of its first occurrence

    for entry in config.names:
        if entry.name in all_name_values:
            raise ConfigError(
                f"Name {entry.name!r} is already used as {all_name_values[entry.name]}"
            )
        all_name_values[entry.name] = "a canonical"

        for match in entry.match:
            if match.name in all_name_values:
                raise ConfigError(
                    f"Name {match.name!r} under canonical {entry.name!r} is already used as {all_name_values[match.name]}"
                )
            all_name_values[match.name] = f"an alias under canonical {entry.name!r}"

    # --- affiliations ---
    canonical_affils: dict[str, str] = {}  # canonical -> list name
    for entry in config.internal_affiliations:
        if entry.canonical in canonical_affils:
            where = canonical_affils[entry.canonical]
            raise ConfigError(
                f"Duplicate affiliation canonical: {entry.canonical!r} (already in {where})"
            )
        canonical_affils[entry.canonical] = "internal_affiliations"
    for entry in config.external_affiliations:
        if entry.canonical in canonical_affils:
            where = canonical_affils[entry.canonical]
            raise ConfigError(
                f"Duplicate affiliation canonical: {entry.canonical!r} (already in {where})"
            )
        canonical_affils[entry.canonical] = "external_affiliations"

    # --- include/exclude/split/no_split/manual_split institution ---
    include_inst = [r.name for r in config.include_institution]
    exclude_inst = [r.name for r in config.exclude_institution]
    split_inst = [r.name for r in config.split_institution]
    no_split_inst = [r.name for r in config.no_split_institution]
    manual_split_inst = [r.name for r in config.manual_split_institution]
    _check_unique_strs("include_institution", include_inst)
    _check_unique_strs("exclude_institution", exclude_inst)
    _check_unique_strs("split_institution", split_inst)
    _check_unique_strs("no_split_institution", no_split_inst)
    _check_unique_strs("manual_split_institution", manual_split_inst)
    _check_disjoint_strs(
        "include_institution",
        set(include_inst),
        "exclude_institution",
        set(exclude_inst),
    )
    _check_disjoint_strs(
        "split_institution",
        set(split_inst),
        "no_split_institution",
        set(no_split_inst),
    )
    _check_disjoint_strs(
        "manual_split_institution",
        set(manual_split_inst),
        "split_institution",
        set(split_inst),
    )
    _check_disjoint_strs(
        "manual_split_institution",
        set(manual_split_inst),
        "no_split_institution",
        set(no_split_inst),
    )

    # --- include/exclude/split/no_split/manual_split dsl ---
    include_dsl = [r.name for r in config.include_dsl]
    exclude_dsl = [r.name for r in config.exclude_dsl]
    split_dsl = [r.name for r in config.split_dsl]
    no_split_dsl = [r.name for r in config.no_split_dsl]
    manual_split_dsl = [r.name for r in config.manual_split_dsl]
    _check_unique_strs("include_dsl", include_dsl)
    _check_unique_strs("exclude_dsl", exclude_dsl)
    _check_unique_strs("split_dsl", split_dsl)
    _check_unique_strs("no_split_dsl", no_split_dsl)
    _check_unique_strs("manual_split_dsl", manual_split_dsl)
    _check_disjoint_strs(
        "include_dsl",
        set(include_dsl),
        "exclude_dsl",
        set(exclude_dsl),
    )
    _check_disjoint_strs(
        "split_dsl",
        set(split_dsl),
        "no_split_dsl",
        set(no_split_dsl),
    )
    _check_disjoint_strs(
        "manual_split_dsl",
        set(manual_split_dsl),
        "split_dsl",
        set(split_dsl),
    )
    _check_disjoint_strs(
        "manual_split_dsl",
        set(manual_split_dsl),
        "no_split_dsl",
        set(no_split_dsl),
    )

    # --- include/exclude paper ---
    include_paper = [r.id for r in config.include_paper]
    exclude_paper = [r.id for r in config.exclude_paper]
    _check_unique_ints("include_paper", include_paper)
    _check_unique_ints("exclude_paper", exclude_paper)
    _check_disjoint_ints(
        "include_paper",
        set(include_paper),
        "exclude_paper",
        set(exclude_paper),
    )

    # --- data-dependent checks ---
    if papers is not None:
        _validate_against_papers(config, papers)


def _validate_against_papers(config: Config, papers: "list[ParsedPaper]") -> None:
    """Checks that are only meaningful when the processed paper data is known."""
    paper_ids = {p.id for p in papers}
    for rule in config.include_paper:
        if rule.id not in paper_ids:
            raise ConfigError(f"include_paper references unknown paper ID: {rule.id}")
    for rule in config.exclude_paper:
        if rule.id not in paper_ids:
            raise ConfigError(f"exclude_paper references unknown paper ID: {rule.id}")

    # Build {trackId: track_name} from the loaded papers.
    paper_tracks: dict[int, str] = {}
    for p in papers:
        if p.trackId is not None and p.track_name is not None:
            paper_tracks[p.trackId] = p.track_name

    for query_rule in config.query:
        for track in query_rule.tracks:
            if track.id not in paper_tracks:
                raise ConfigError(
                    f"Query references track ID {track.id} ({track.name!r}) which has no papers in the current data"
                )
            actual = paper_tracks[track.id]
            if actual != track.name:
                raise ConfigError(
                    f"Track {track.id} name mismatch: config has {track.name!r}, data has {actual!r}"
                )

    # Each individual (author, single-affiliation) combination must match at most
    # one canonical.  Authors may list multiple affiliations; each is checked
    # independently because match rules are written per individual affiliation.
    checked: set[str] = set()
    for paper in papers:
        for author in paper.authors:
            for affil in author.affiliations:
                key = affiliation_key(author.name, [affil])
                if key in checked:
                    continue
                checked.add(key)
                matches = find_all_matching_affiliations(config, author.name, [affil])
                if len(matches) > 1:
                    canonicals = ", ".join(repr(m.canonical) for m in matches)
                    raise ConfigError(
                        f"Author {author.name!r} affiliation {affil.institution!r} matches multiple canonical affiliations: {canonicals}"
                    )


# ---------------------------------------------------------------------------
# ConfigDocument
# ---------------------------------------------------------------------------


class ConfigDocument:
    """
    Wraps a conference config file.

    Loads into a Pydantic Config model at construction.  All mutations go
    through apply(), which clones the config, runs the mutation, validates
    the result, and either saves (on success) or reverts (on ConfigError).

    Use try_apply() to speculatively test whether a mutation would produce a
    valid config without committing any changes.
    """

    _path: pathlib.Path
    config: Config

    def __init__(self, path: pathlib.Path) -> None:
        self._path = path
        self.config = load_config(path)
        validate_config(self.config)

    # ------------------------------------------------------------------
    # Core mutation primitives
    # ------------------------------------------------------------------

    def apply(
        self,
        mutate: Callable[[Config], None],
        papers: "list[ParsedPaper] | None" = None,
    ) -> None:
        """
        Apply a mutation, validate the result, and save.

        The mutate function receives self.config directly and may modify it
        in place.  If validate_config raises ConfigError (including errors
        raised by the mutate function itself), the config is restored to its
        pre-mutation state and the error is re-raised.
        """
        backup = self.config.model_copy(deep=True)
        try:
            mutate(self.config)
            validate_config(self.config, papers)
        except ConfigError:
            self.config = backup
            raise
        self._save()

    def try_apply(
        self,
        mutate: Callable[[Config], None],
        papers: "list[ParsedPaper] | None" = None,
    ) -> bool:
        """
        Return True if the mutation would produce a valid config, without saving.

        Uses a deep clone so self.config is never modified.
        """
        trial = self.config.model_copy(deep=True)
        try:
            mutate(trial)
            validate_config(trial, papers)
            return True
        except ConfigError:
            return False

    # ------------------------------------------------------------------
    # Name operations
    # ------------------------------------------------------------------

    def add_name(self, name: str) -> None:
        def _mutate(config: Config) -> None:
            config.names.append(NameEntry(name=name))

        self.apply(_mutate)

    def add_name_alias(self, canonical: str, alias: str) -> None:
        def _mutate(config: Config) -> None:
            for entry in config.names:
                if entry.name == canonical:
                    entry.match.append(NameMatch(name=alias))
                    return
            raise ConfigError(f"Name canonical not found: {canonical!r}")

        self.apply(_mutate)

    def remove_name(self, name: str) -> None:
        def _mutate(config: Config) -> None:
            config.names = [e for e in config.names if e.name != name]

        self.apply(_mutate)

    def remove_name_alias(self, canonical: str, alias: str) -> None:
        def _mutate(config: Config) -> None:
            for entry in config.names:
                if entry.name == canonical:
                    entry.match = [m for m in entry.match if m.name != alias]
                    return
            raise ConfigError(f"Name canonical not found: {canonical!r}")

        self.apply(_mutate)

    # ------------------------------------------------------------------
    # Affiliation operations
    # ------------------------------------------------------------------

    def add_affiliation(
        self,
        canonical: str,
        match_rules: list[AffiliationMatchRule],
        internal: bool,
        papers: "list[ParsedPaper] | None" = None,
    ) -> None:
        def _mutate(config: Config) -> None:
            target = (
                config.internal_affiliations
                if internal
                else config.external_affiliations
            )
            named = [r for r in match_rules if r.name is not None]
            unnamed = [r for r in match_rules if r.name is None]
            target.append(
                AffiliationEntry(
                    canonical=canonical, match=unnamed, match_for_name=named
                )
            )

        self.apply(_mutate, papers)

    def add_affiliation_match_rule(
        self,
        canonical: str,
        match_rule: AffiliationMatchRule,
        papers: "list[ParsedPaper] | None" = None,
    ) -> None:
        def _mutate(config: Config) -> None:
            for entry in config.internal_affiliations + config.external_affiliations:
                if entry.canonical == canonical:
                    if match_rule.name is not None:
                        entry.match_for_name.append(match_rule)
                    else:
                        entry.match.append(match_rule)
                    return
            raise ConfigError(f"Affiliation canonical not found: {canonical!r}")

        self.apply(_mutate, papers)

    def remove_affiliation(self, canonical: str) -> None:
        def _mutate(config: Config) -> None:
            config.internal_affiliations = [
                e for e in config.internal_affiliations if e.canonical != canonical
            ]
            config.external_affiliations = [
                e for e in config.external_affiliations if e.canonical != canonical
            ]

        self.apply(_mutate)

    def remove_affiliation_match_rule(
        self, canonical: str, rule: AffiliationMatchRule
    ) -> None:
        """Remove a specific match rule from the entry identified by canonical.

        Removes by value equality so it is correct regardless of list sort order.
        """

        def _mutate(config: Config) -> None:
            for entry in config.internal_affiliations + config.external_affiliations:
                if entry.canonical == canonical:
                    target = (
                        entry.match_for_name if rule.name is not None else entry.match
                    )
                    try:
                        target.remove(rule)
                    except ValueError:
                        list_name = (
                            "match_for_name" if rule.name is not None else "match"
                        )
                        raise ConfigError(
                            f"Match rule not found in {canonical!r} {list_name}"
                        )
                    return
            raise ConfigError(f"Affiliation canonical not found: {canonical!r}")

        self.apply(_mutate)

    # ------------------------------------------------------------------
    # Query / institution / dsl / paper operations
    # ------------------------------------------------------------------

    def add_query(self, rule: QueryRule) -> None:
        self.apply(lambda config: config.query.append(rule))

    def set_query(self, rule: QueryRule) -> None:
        """Replace all existing query rules with a single rule."""
        self.apply(lambda config: setattr(config, "query", [rule]))

    def add_include_institution(self, name: str, comment: str | None = None) -> None:
        self.apply(
            lambda config: config.include_institution.append(
                InstitutionRule(name=name, comment=comment)
            )
        )

    def add_exclude_institution(self, name: str, comment: str | None = None) -> None:
        self.apply(
            lambda config: config.exclude_institution.append(
                InstitutionRule(name=name, comment=comment)
            )
        )

    def add_split_institution(self, name: str) -> None:
        self.apply(
            lambda config: config.split_institution.append(InstitutionRule(name=name))
        )

    def add_no_split_institution(self, name: str) -> None:
        self.apply(
            lambda config: config.no_split_institution.append(
                InstitutionRule(name=name)
            )
        )

    def add_include_dsl(self, name: str, comment: str | None = None) -> None:
        self.apply(
            lambda config: config.include_dsl.append(
                DslRule(name=name, comment=comment)
            )
        )

    def add_exclude_dsl(self, name: str, comment: str | None = None) -> None:
        self.apply(
            lambda config: config.exclude_dsl.append(
                DslRule(name=name, comment=comment)
            )
        )

    def add_split_dsl(self, name: str) -> None:
        self.apply(lambda config: config.split_dsl.append(DslRule(name=name)))

    def add_no_split_dsl(self, name: str) -> None:
        self.apply(lambda config: config.no_split_dsl.append(DslRule(name=name)))

    def add_manual_split_institution(
        self,
        name: str,
        parts: list[str],
        papers: "list[ParsedPaper] | None" = None,
    ) -> None:
        rule = ManualSplitRule(name=name, parts=list(parts))
        self.apply(lambda config: config.manual_split_institution.append(rule), papers)

    def add_manual_split_dsl(
        self,
        name: str,
        parts: list[str],
        papers: "list[ParsedPaper] | None" = None,
    ) -> None:
        rule = ManualSplitRule(name=name, parts=list(parts))
        self.apply(lambda config: config.manual_split_dsl.append(rule), papers)

    def add_include_paper(self, id: int, comment: str | None = None) -> None:
        self.apply(
            lambda config: config.include_paper.append(
                PaperRule(id=id, comment=comment)
            )
        )

    def add_exclude_paper(self, id: int, comment: str | None = None) -> None:
        self.apply(
            lambda config: config.exclude_paper.append(
                PaperRule(id=id, comment=comment)
            )
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _save(self) -> None:
        save_config(self._path, self.config)
