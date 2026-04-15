"""Paper normalization steps — names, affiliations, and apply mappings."""

from typing import override

from confer_parse_dub.exceptions import ConfigError, QuitRequested
from confer_parse_dub.io.parse import parse_tracks
from confer_parse_dub.io.state_io import save_state
from confer_parse_dub.io.undo import undo_last_decision
from confer_parse_dub.models.config import AffiliationMatchRule, AffiliationPatternItem
from confer_parse_dub.models.paper import Affiliation, ParsedPaper
from confer_parse_dub.models.state import Decision, DecisionType
from confer_parse_dub.processing.normalize_affiliations import (
    affiliation_key,
    find_canonical_affiliation,
    is_internal_affiliation,
)
from confer_parse_dub.processing.normalize_names import find_canonical_name
from confer_parse_dub.steps.context import UI, RunContext, Step, UIChoice


class NormalizePapersStep(Step):
    """Compute pending papers and return per-paper normalization steps."""

    @override
    def execute(self, context: RunContext) -> list[Step]:
        _apply_splits(context)
        pending = [p for p in context.papers if _paper_needs_work(context, p)]

        total_names = len(context.config_doc.config.names)
        total_affiliations = len(context.config_doc.config.internal_affiliations) + len(
            context.config_doc.config.external_affiliations
        )

        if not pending:
            context.ui.print("=== Normalization ===")
            context.ui.print(
                "{} canonical name(s), {} canonical affiliation(s) — all resolved.".format(
                    total_names, total_affiliations
                )
            )
            skipped_names = len(context.state.skipped_names)
            skipped_affiliations = len(context.state.skipped_affiliations)
            if skipped_names or skipped_affiliations:
                context.ui.print(
                    (
                        "  {} name(s) and {} affiliation(s) pending "
                        "(run with --review-skipped to revisit)."
                    ).format(skipped_names, skipped_affiliations)
                )
            context.ui.print()
            return [ApplyMappingsStep()]

        context.ui.print("=== Normalization ===")
        context.ui.print(
            "{} paper(s) have unresolved names or affiliations.".format(len(pending))
        )

        tracks = parse_tracks(context.config_doc.config)
        steps: list[Step] = []
        for i, paper in enumerate(pending):
            steps.append(PaperNormalizationStep(paper, i + 1, len(pending), tracks))
        steps.append(ApplyMappingsStep())
        return steps


class ApplyMappingsStep(Step):
    """Apply all resolved canonical name and affiliation mappings to papers."""

    @override
    def execute(self, context: RunContext) -> list[Step]:
        config = context.config_doc.config
        for paper in context.papers:
            for author in paper.authors:
                canonical_name = find_canonical_name(config, author.name)
                if canonical_name is not None:
                    author.name = canonical_name
                    for affil in author.affiliations:
                        canonical_affil = find_canonical_affiliation(
                            config, canonical_name, [affil]
                        )
                        if canonical_affil is not None:
                            if canonical_affil not in author.canonical_affiliations:
                                author.canonical_affiliations.append(canonical_affil)
        return []


class PaperNormalizationStep(Step):
    """Print a paper header and queue name/affiliation resolution steps for it."""

    def __init__(
        self,
        paper: ParsedPaper,
        index: int,
        total: int,
        tracks: dict[int, str],
    ) -> None:
        self._paper: ParsedPaper = paper
        self._index: int = index
        self._total: int = total
        self._tracks: dict[int, str] = tracks

    @override
    def execute(self, context: RunContext) -> list[Step]:
        ui = context.ui
        config = context.config_doc.config
        state = context.state
        paper = self._paper

        if paper.trackId is None:
            track_name = "Track (unassigned)"
        else:
            track_name = self._tracks.get(
                paper.trackId, "Track {}".format(paper.trackId)
            )
        ui.print()
        ui.print("--- Paper {} of {} ---".format(self._index, self._total))
        ui.print('"{}"'.format(paper.title))
        ui.print("{}".format(track_name))
        ui.print()
        ui.print("  Authors:")
        for author in paper.authors:
            canonical_name = find_canonical_name(config, author.name)
            name_display = canonical_name if canonical_name else author.name

            if canonical_name is None:
                status = (
                    "(name skipped)"
                    if author.name in state.skipped_names
                    else "(name unresolved)"
                )
                ui.print("    {}  {}".format(name_display, status))
            else:
                ui.print("    {}".format(name_display))
                for affil in author.affiliations:
                    canonical_affil = find_canonical_affiliation(
                        config, canonical_name, [affil]
                    )
                    key = affiliation_key(canonical_name, [affil])
                    inst_label = affil.institution or affil.dsl or "(no institution)"
                    if canonical_affil is not None:
                        affil_status = "→ {}".format(canonical_affil)
                    elif key in state.skipped_affiliations:
                        affil_status = "(skipped)"
                    else:
                        affil_status = "(unresolved)"
                    ui.print("      {} {}".format(inst_label, affil_status))
        ui.print()

        # Name resolution steps first; affiliation steps computed after names resolve.
        name_steps: list[Step] = []
        for author in paper.authors:
            if find_canonical_name(config, author.name) is not None:
                continue
            if author.name in state.skipped_names and not context.review_skipped:
                continue
            name_steps.append(
                ResolveNameStep(author.name, author.affiliations, paper.title)
            )

        return name_steps + [ResolveAffilsForPaperStep(paper)]


class ResolveAffilsForPaperStep(Step):
    """Compute and queue affiliation resolution steps for one paper."""

    def __init__(self, paper: ParsedPaper) -> None:
        self._paper: ParsedPaper = paper

    @override
    def execute(self, context: RunContext) -> list[Step]:
        config = context.config_doc.config
        state = context.state
        steps: list[Step] = []
        for author in self._paper.authors:
            canonical_name = find_canonical_name(config, author.name)
            if canonical_name is None:
                continue
            for affil in author.affiliations:
                if (
                    find_canonical_affiliation(config, canonical_name, [affil])
                    is not None
                ):
                    continue
                key = affiliation_key(canonical_name, [affil])
                if key in state.skipped_affiliations and not context.review_skipped:
                    continue
                steps.append(
                    ResolveAffiliationStep(
                        canonical_name, [affil], key, self._paper.title
                    )
                )
        return steps


class ResolveNameStep(Step):
    """Prompt the user to resolve one unrecognized author name."""

    def __init__(
        self,
        raw_name: str,
        affiliations: list[Affiliation] | None = None,
        paper_title: str | None = None,
    ) -> None:
        self._raw_name: str = raw_name
        self._affiliations: list[Affiliation] = affiliations or []
        self._paper_title: str | None = paper_title

    @override
    def execute(self, context: RunContext) -> list[Step]:
        config_doc = context.config_doc
        state = context.state
        path_state = context.path_state
        ui = context.ui
        raw_name = self._raw_name

        # May have been resolved by a prior step (e.g. after undo).
        if find_canonical_name(config_doc.config, raw_name) is not None:
            return []
        if raw_name in state.skipped_names and not context.review_skipped:
            return []

        if context.browser is not None:
            context.browser.navigate_for_name(
                raw_name, self._affiliations, self._paper_title
            )

        ui.print()
        ui.print("  Name: '{}'".format(raw_name))

        undo_label = (
            "Undo last decision ({})".format(state.history[-1].summary)
            if state.history
            else None
        )

        USE_AS_CANONICAL = "Use '{}' as canonical".format(raw_name)
        EDIT_AS_CANONICAL = "Edit as canonical..."
        ALIAS_TO_ANOTHER = "Alias to another canonical"
        SKIP = "Skip for now"
        QUIT = "Quit"

        choices = [
            UIChoice(title=USE_AS_CANONICAL, shortcut_key="u"),
            UIChoice(title=EDIT_AS_CANONICAL, shortcut_key="e"),
            UIChoice(title=ALIAS_TO_ANOTHER, shortcut_key="a"),
            UIChoice(title=SKIP, shortcut_key="s"),
        ]
        if undo_label:
            choices.append(UIChoice(title=undo_label, shortcut_key="z"))
        choices.append(UIChoice(title=QUIT, shortcut_key="q"))

        action = ui.select("  Name:", choices)
        if action is None or action == QUIT:
            raise QuitRequested()

        if undo_label and action == undo_label:
            decision = undo_last_decision(config_doc, state, path_state)
            if decision:
                ui.print("  Undone: {}".format(decision.summary))
            return [self]  # Re-queue to re-prompt after undo.

        if action == SKIP:
            if raw_name not in state.skipped_names:
                state.skipped_names.append(raw_name)
            state.history.append(
                Decision(
                    type=DecisionType.SKIP_NAME,
                    summary="Skipped name '{}'".format(raw_name),
                    name=raw_name,
                )
            )
            save_state(state, path_state)
            return []

        if action == USE_AS_CANONICAL:
            canonical = raw_name
            config_doc.add_name(canonical)
            state.history.append(
                Decision(
                    type=DecisionType.ADD_NAME,
                    summary="Added '{}' as canonical name".format(canonical),
                    name=raw_name,
                )
            )

        elif action == EDIT_AS_CANONICAL:
            edited = ui.text("  Canonical name:", default=raw_name)
            if edited is None:
                raise QuitRequested()
            canonical = edited.strip() or raw_name
            config_doc.add_name(canonical)
            if canonical != raw_name:
                config_doc.add_name_alias(canonical, raw_name)
            state.history.append(
                Decision(
                    type=DecisionType.ADD_NAME,
                    summary="Added '{}' as canonical name".format(canonical),
                    name=raw_name,
                )
            )

        elif action == ALIAS_TO_ANOTHER:
            existing = [entry.name for entry in config_doc.config.names]
            typed = ui.autocomplete(
                "  Canonical name for '{}'?".format(raw_name), existing
            )
            if typed is None:
                raise QuitRequested()

            typed_cf = typed.casefold()
            canonical = next((c for c in existing if c.casefold() == typed_cf), None)

            if canonical is None:
                ui.print("  No valid canonical selected. Skipping.")
                if raw_name not in state.skipped_names:
                    state.skipped_names.append(raw_name)
                state.history.append(
                    Decision(
                        type=DecisionType.SKIP_NAME,
                        summary="Skipped name '{}' (no canonical selected)".format(
                            raw_name
                        ),
                        name=raw_name,
                    )
                )
                save_state(state, path_state)
                return []

            config_doc.add_name_alias(canonical, raw_name)
            state.history.append(
                Decision(
                    type=DecisionType.ADD_NAME_ALIAS,
                    summary="Mapped '{}' as alias for '{}'".format(raw_name, canonical),
                    name=raw_name,
                    canonical=canonical,
                )
            )

        if raw_name in state.skipped_names:
            state.skipped_names.remove(raw_name)
        save_state(state, path_state)
        return []


class ResolveAffiliationStep(Step):
    """Prompt the user to resolve one unrecognized affiliation."""

    def __init__(
        self,
        author_name: str,
        affiliations: list[Affiliation],
        key: str,
        paper_title: str | None = None,
    ) -> None:
        self._author_name: str = author_name
        self._affiliations: list[Affiliation] = affiliations
        self._key: str = key
        self._paper_title: str | None = paper_title

    @override
    def execute(self, context: RunContext) -> list[Step]:
        config_doc = context.config_doc
        state = context.state
        path_state = context.path_state
        ui = context.ui
        author_name = self._author_name
        affiliations = self._affiliations
        key = self._key

        # May have been resolved by a prior step or undo.
        canonical_name = find_canonical_name(config_doc.config, author_name)
        if canonical_name is None:
            return []
        if (
            find_canonical_affiliation(config_doc.config, canonical_name, affiliations)
            is not None
        ):
            return []
        if key in state.skipped_affiliations and not context.review_skipped:
            return []

        internal = is_internal_affiliation(config_doc.config, affiliations)

        # When internal and all DSL values are empty, always match on
        # institution + DSL + author name — no need to ask.
        auto_match_rule: AffiliationMatchRule | None = None
        if internal and not any(a.dsl for a in affiliations):
            # Use institution + exact DSL (empty string) + author name.
            # Explicitly matching dsl="" (rather than dsl=None/"ignore DSL") keeps
            # this rule from accidentally matching a second affiliation of the same
            # person at the same institution that carries a non-empty DSL.
            auto_match_rule = AffiliationMatchRule(
                name=author_name,
                affiliations=[
                    AffiliationPatternItem(institution=a.institution, dsl=a.dsl)
                    for a in affiliations
                    if a.institution
                ],
            )

        if context.browser is not None:
            context.browser.navigate_for_affiliation(
                affiliations,
                author_name=author_name,
                paper_title=self._paper_title,
                internal=internal,
            )

        ui.print()
        ui.print(
            "  Affiliation for '{}' ({})".format(
                author_name, "internal" if internal else "external"
            )
        )
        for affil in affiliations:
            if affil.institution:
                ui.print("    institution: '{}'".format(affil.institution))
            if affil.dsl:
                ui.print("    dsl: '{}'".format(affil.dsl))
        if not affiliations:
            ui.print("    (no affiliations listed)")

        all_entries = (
            config_doc.config.internal_affiliations
            + config_doc.config.external_affiliations
        )
        existing_canonicals = [e.canonical for e in all_entries]
        single_institution = (
            affiliations[0].institution
            if len(affiliations) == 1 and affiliations[0].institution
            else None
        )
        edit_default = single_institution or (
            affiliations[0].institution if affiliations else ""
        )

        undo_label = (
            "Undo last decision ({})".format(state.history[-1].summary)
            if state.history
            else None
        )

        USE_AS_CANONICAL = (
            "Use '{}' as canonical".format(single_institution)
            if single_institution
            else None
        )
        EDIT_AS_CANONICAL = "Edit as canonical..."
        ALIAS_TO_ANOTHER = "Alias to another canonical"
        SPLIT = "Split into separate affiliations..."
        SKIP = "Skip for now"
        QUIT = "Quit"

        choices: list[UIChoice] = []
        if USE_AS_CANONICAL:
            choices.append(UIChoice(title=USE_AS_CANONICAL, shortcut_key="u"))
        choices += [
            UIChoice(title=EDIT_AS_CANONICAL, shortcut_key="e"),
            UIChoice(title=ALIAS_TO_ANOTHER, shortcut_key="a"),
            UIChoice(title=SPLIT, shortcut_key="l"),
        ]
        choices.append(UIChoice(title=SKIP, shortcut_key="s"))
        if undo_label:
            choices.append(UIChoice(title=undo_label, shortcut_key="z"))
        choices.append(UIChoice(title=QUIT, shortcut_key="q"))

        action = ui.select("  Affiliation:", choices)
        if action is None or action == QUIT:
            raise QuitRequested()

        if undo_label and action == undo_label:
            decision = undo_last_decision(config_doc, state, path_state)
            if decision:
                ui.print("  Undone: {}".format(decision.summary))
            return [self]  # Re-queue to re-prompt after undo.

        if action == SKIP:
            if key not in state.skipped_affiliations:
                state.skipped_affiliations.append(key)
            state.history.append(
                Decision(
                    type=DecisionType.SKIP_AFFILIATION,
                    summary="Skipped affiliation for '{}'".format(author_name),
                    key=key,
                )
            )
            save_state(state, path_state)
            return []

        if action == SPLIT:
            split_steps = _do_split(
                ui, affiliations, author_name, self._paper_title, context
            )
            if split_steps is None:
                return [self]  # cancelled — re-prompt
            return split_steps

        if action == USE_AS_CANONICAL:
            assert single_institution is not None
            canonical = single_institution
            match_rules: list[AffiliationMatchRule] = []
            try:
                config_doc.add_affiliation(
                    canonical, match_rules, internal=internal, papers=context.papers
                )
            except ConfigError as exc:
                ui.print("  Error: {}".format(exc))
                return [self]
            state.history.append(
                Decision(
                    type=DecisionType.ADD_AFFILIATION,
                    summary="Added '{}' as canonical affiliation".format(canonical),
                    canonical=canonical,
                )
            )

        elif action == EDIT_AS_CANONICAL:
            edited = ui.text(
                "  Canonical affiliation name:", default=edit_default or ""
            )
            if edited is None:
                raise QuitRequested()
            canonical = edited.strip()
            if not canonical:
                if key not in state.skipped_affiliations:
                    state.skipped_affiliations.append(key)
                state.history.append(
                    Decision(
                        type=DecisionType.SKIP_AFFILIATION,
                        summary="Skipped affiliation for '{}' (no name entered)".format(
                            author_name
                        ),
                        key=key,
                    )
                )
                save_state(state, path_state)
                return []
            if auto_match_rule is not None:
                match_rule = auto_match_rule
            else:
                match_rule = _ask_match_fields(ui, author_name, affiliations)
                if match_rule is None:
                    raise QuitRequested()
            try:
                config_doc.add_affiliation(
                    canonical, [match_rule], internal=internal, papers=context.papers
                )
            except ConfigError as exc:
                ui.print("  Error: {}".format(exc))
                return [self]
            state.history.append(
                Decision(
                    type=DecisionType.ADD_AFFILIATION,
                    summary="Added '{}' as canonical affiliation".format(canonical),
                    canonical=canonical,
                )
            )

        elif action == ALIAS_TO_ANOTHER:
            typed = ui.autocomplete("  Canonical affiliation:", existing_canonicals)
            if typed is None:
                raise QuitRequested()

            typed_cf = typed.casefold()
            canonical = next(
                (c for c in existing_canonicals if c.casefold() == typed_cf), None
            )

            if canonical is None:
                ui.print("  No valid canonical selected. Skipping.")
                if key not in state.skipped_affiliations:
                    state.skipped_affiliations.append(key)
                state.history.append(
                    Decision(
                        type=DecisionType.SKIP_AFFILIATION,
                        summary="Skipped affiliation for '{}' (no canonical selected)".format(
                            author_name
                        ),
                        key=key,
                    )
                )
                save_state(state, path_state)
                return []

            if auto_match_rule is not None:
                match_rule = auto_match_rule
            else:
                match_rule = _ask_match_fields(ui, author_name, affiliations)
                if match_rule is None:
                    raise QuitRequested()
            try:
                config_doc.add_affiliation_match_rule(
                    canonical, match_rule, papers=context.papers
                )
            except ConfigError as exc:
                ui.print("  Error: {}".format(exc))
                return [self]
            state.history.append(
                Decision(
                    type=DecisionType.ADD_AFFILIATION_MATCH_RULE,
                    summary="Mapped affiliation for '{}' to '{}'".format(
                        author_name, canonical
                    ),
                    canonical=canonical,
                    match_rule=match_rule,
                )
            )

        if key in state.skipped_affiliations:
            state.skipped_affiliations.remove(key)
        save_state(state, path_state)
        return []


class ReviewSplitsStep(Step):
    """
    Pre-normalization pass: ask yes/no for each affiliation value that contains
    a character (currently '/') that may indicate multiple values to be split.

    Decisions are stored in config so they persist across state resets.
    """

    @override
    def execute(self, context: RunContext) -> list[Step]:
        config = context.config_doc.config
        already_decided = (
            {r.name for r in config.split_institution}
            | {r.name for r in config.no_split_institution}
            | {r.name for r in config.split_dsl}
            | {r.name for r in config.no_split_dsl}
        )

        # Collect undecided slash values keyed by (value, field).
        # Track the first author name and all papers where the value appears.
        new_values: dict[tuple[str, str], list[str]] = {}
        first_author: dict[tuple[str, str], str] = {}
        papers_seen: dict[tuple[str, str], list[ParsedPaper]] = {}
        paper_ids_seen: dict[tuple[str, str], set[int]] = {}
        for paper in context.papers:
            for author in paper.authors:
                for affil in author.affiliations:
                    for field, value in (
                        ("institution", affil.institution),
                        ("dsl", affil.dsl),
                    ):
                        if not value or "/" not in value or value in already_decided:
                            continue
                        key = (value, field)
                        if key not in new_values:
                            parts = [p.strip() for p in value.split("/") if p.strip()]
                            if len(parts) > 1:
                                new_values[key] = parts
                                first_author[key] = author.name
                                papers_seen[key] = []
                                paper_ids_seen[key] = set()
                        if key in papers_seen and paper.id not in paper_ids_seen[key]:
                            papers_seen[key].append(paper)
                            paper_ids_seen[key].add(paper.id)

        if not new_values:
            return []

        steps: list[Step] = [
            ReviewSplitStep(
                value,
                parts,
                field,
                author_name=first_author.get((value, field)),
                papers=papers_seen.get((value, field), []),
            )
            for (value, field), parts in sorted(new_values.items())
        ]
        return steps


class ReviewSplitStep(Step):
    """Ask the user whether one affiliation value that contains a split character should be split."""

    def __init__(
        self,
        value: str,
        parts: list[str],
        field: str,
        author_name: str | None = None,
        papers: list[ParsedPaper] | None = None,
    ) -> None:
        self._value: str = value
        self._parts: list[str] = parts
        self._field: str = field  # "institution" or "dsl"
        self._author_name: str | None = author_name
        self._papers: list[ParsedPaper] = papers or []

    @override
    def execute(self, context: RunContext) -> list[Step]:
        ui = context.ui
        config_doc = context.config_doc

        if context.browser is not None:
            context.browser.navigate_for_split(
                self._value, self._parts, self._author_name
            )

        ui.print()
        ui.print(
            "  {} '{}' contains '/' ({} paper(s))".format(
                self._field.capitalize(), self._value, len(self._papers)
            )
        )
        if self._author_name:
            ui.print("  First seen for: {}".format(self._author_name))
        for paper in self._papers[:3]:
            ui.print("    - {}".format(paper.title[:72]))
        if len(self._papers) > 3:
            ui.print("    ... and {} more.".format(len(self._papers) - 3))
        ui.print(
            "  Split into: {}".format(", ".join("'{}'".format(p) for p in self._parts))
        )

        split = ui.confirm("Split?", default=True)
        if split is None:
            raise QuitRequested()

        if self._field == "institution":
            if split:
                config_doc.add_split_institution(self._value)
            else:
                config_doc.add_no_split_institution(self._value)
        else:
            if split:
                config_doc.add_split_dsl(self._value)
            else:
                config_doc.add_no_split_dsl(self._value)

        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_splits(context: RunContext) -> None:
    """Replace affiliations in context.papers according to all split rules in config."""
    config = context.config_doc.config
    split_institutions = {r.name for r in config.split_institution}
    split_dsls = {r.name for r in config.split_dsl}
    manual_split_inst = {r.name: r.parts for r in config.manual_split_institution}
    manual_split_dsl = {r.name: r.parts for r in config.manual_split_dsl}
    if (
        not split_institutions
        and not split_dsls
        and not manual_split_inst
        and not manual_split_dsl
    ):
        return
    for paper in context.papers:
        for author in paper.authors:
            new_affiliations: list[Affiliation] = []
            for affil in author.affiliations:
                if affil.institution in split_institutions:
                    parts = [
                        p.strip() for p in affil.institution.split("/") if p.strip()
                    ]
                    for part in parts:
                        new_affiliations.append(
                            affil.model_copy(update={"institution": part})
                        )
                elif affil.institution in manual_split_inst:
                    for part in manual_split_inst[affil.institution]:
                        new_affiliations.append(
                            affil.model_copy(update={"institution": part})
                        )
                elif affil.dsl in split_dsls:
                    parts = [p.strip() for p in affil.dsl.split("/") if p.strip()]
                    for part in parts:
                        new_affiliations.append(affil.model_copy(update={"dsl": part}))
                elif affil.dsl in manual_split_dsl:
                    for part in manual_split_dsl[affil.dsl]:
                        new_affiliations.append(affil.model_copy(update={"dsl": part}))
                else:
                    new_affiliations.append(affil)
            author.affiliations = new_affiliations


def _ask_match_fields(
    ui: UI,
    author_name: str,
    affiliations: list[Affiliation],
) -> AffiliationMatchRule | None:
    """Ask the user which fields should define the match rule."""
    INSTITUTION = "Institution only"
    INSTITUTION_DSL = "Institution + DSL"
    INSTITUTION_AUTHOR = "Institution + author name"
    INSTITUTION_DSL_AUTHOR = "Institution + DSL + author name"

    result = ui.select(
        "  Match on which fields?",
        [
            UIChoice(title=INSTITUTION, shortcut_key="i"),
            UIChoice(title=INSTITUTION_DSL, shortcut_key="d"),
            UIChoice(title=INSTITUTION_AUTHOR, shortcut_key="n"),
            UIChoice(title=INSTITUTION_DSL_AUTHOR, shortcut_key="a"),
        ],
    )
    if result is None:
        return None

    if result == INSTITUTION:
        return AffiliationMatchRule(
            affiliations=[
                AffiliationPatternItem(institution=a.institution)
                for a in affiliations
                if a.institution
            ]
        )

    if result == INSTITUTION_DSL:
        return AffiliationMatchRule(
            affiliations=[
                AffiliationPatternItem(institution=a.institution, dsl=a.dsl or None)
                for a in affiliations
                if a.institution
            ]
        )

    if result == INSTITUTION_AUTHOR:
        return AffiliationMatchRule(
            name=author_name,
            affiliations=[
                AffiliationPatternItem(institution=a.institution)
                for a in affiliations
                if a.institution
            ],
        )

    # INSTITUTION_DSL_AUTHOR
    return AffiliationMatchRule(
        name=author_name,
        affiliations=[
            AffiliationPatternItem(institution=a.institution, dsl=a.dsl or None)
            for a in affiliations
            if a.institution
        ],
    )


def _do_split(
    ui: UI,
    affiliations: list[Affiliation],
    author_name: str,
    paper_title: str | None,
    context: RunContext,
) -> "list[Step] | None":
    """
    Handle the Split action from ResolveAffiliationStep.

    Asks the user which field to split and what the parts are, records the
    split in config (so it persists), re-applies all splits to context.papers,
    then returns new ResolveAffiliationStep instances for each unresolved part.

    Returns None if the user cancelled or provided fewer than 2 parts (caller
    should re-queue the original step).  Returns a list (possibly empty) on
    success.
    """
    affil = affiliations[0] if affiliations else None
    if affil is None:
        ui.print("  No affiliation to split.")
        return None

    has_inst = bool(affil.institution)
    has_dsl = bool(affil.dsl)

    if not has_inst and not has_dsl:
        ui.print("  No institution or DSL value to split.")
        return None

    if has_inst and has_dsl:
        field_result = ui.select(
            "  Split which field?",
            [
                UIChoice(title="Institution", shortcut_key="i"),
                UIChoice(title="DSL", shortcut_key="d"),
            ],
        )
        if field_result is None:
            raise QuitRequested()
        split_field = "institution" if field_result == "Institution" else "dsl"
    else:
        split_field = "institution" if has_inst else "dsl"

    original_value = affil.institution if split_field == "institution" else affil.dsl
    ui.print("  Current {}: '{}'".format(split_field, original_value))
    entered = ui.text(
        "  Enter parts separated by ' / ':",
        default=original_value,
    )
    if entered is None:
        raise QuitRequested()

    parts = [p.strip() for p in entered.split("/") if p.strip()]
    if len(parts) < 2:
        ui.print("  Need at least 2 parts — cancelling split.")
        return None

    try:
        if split_field == "institution":
            context.config_doc.add_manual_split_institution(
                original_value, parts, context.papers
            )
        else:
            context.config_doc.add_manual_split_dsl(
                original_value, parts, context.papers
            )
    except ConfigError as exc:
        ui.print("  Error: {}".format(exc))
        return None

    _apply_splits(context)

    # Return a ResolveAffiliationStep for each split part that isn't yet resolved.
    if split_field == "institution":
        new_affils = [affil.model_copy(update={"institution": p}) for p in parts]
    else:
        new_affils = [affil.model_copy(update={"dsl": p}) for p in parts]

    steps: list[Step] = []
    for new_affil in new_affils:
        new_key = affiliation_key(author_name, [new_affil])
        if (
            find_canonical_affiliation(
                context.config_doc.config, author_name, [new_affil]
            )
            is None
        ):
            steps.append(
                ResolveAffiliationStep(author_name, [new_affil], new_key, paper_title)
            )
    return steps


def _paper_needs_work(context: RunContext, paper: ParsedPaper) -> bool:
    """Return True if the paper has any author with an unresolved name or affiliation."""
    config = context.config_doc.config
    state = context.state
    for author in paper.authors:
        canonical_name = find_canonical_name(config, author.name)
        if canonical_name is None:
            if author.name not in state.skipped_names or context.review_skipped:
                return True
            continue
        for affil in author.affiliations:
            key = affiliation_key(canonical_name, [affil])
            if find_canonical_affiliation(config, canonical_name, [affil]) is None:
                if key not in state.skipped_affiliations or context.review_skipped:
                    return True
    return False
