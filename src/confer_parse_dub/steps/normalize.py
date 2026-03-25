"""Paper normalization steps — names, affiliations, and apply mappings."""

from confer_parse_dub.exceptions import ConfigError, QuitRequested
from confer_parse_dub.io.state_io import save_state
from confer_parse_dub.models.config import AffiliationMatchRule, AffiliationPatternItem
from confer_parse_dub.models.paper import Affiliation, ParsedPaper
from confer_parse_dub.models.state import Decision, DecisionType
from confer_parse_dub.processing.normalize_affiliations import (
    affiliation_key,
    find_canonical_affiliation,
)
from confer_parse_dub.processing.normalize_names import find_canonical_name
from confer_parse_dub.io.parse import parse_tracks
from confer_parse_dub.io.undo import undo_last_decision
from confer_parse_dub.steps.context import UI, RunContext, Step, UIChoice
from confer_parse_dub.steps.pipeline import ApplyMappingsStep


class NormalizePapersStep(Step):
    """Compute pending papers and return per-paper normalization steps."""

    def execute(self, context: RunContext) -> list[Step]:
        pending = [p for p in context.papers if _paper_needs_work(context, p)]

        total_names = len(context.config_doc.config.names)
        total_affiliations = len(
            context.config_doc.config.internal_affiliations
        ) + len(context.config_doc.config.external_affiliations)

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
                    "  {} name(s) and {} affiliation(s) pending"
                    " (run with --review-skipped to revisit).".format(
                        skipped_names, skipped_affiliations
                    )
                )
            skipped_multi = len(context.state.skipped_multi_affiliations)
            if skipped_multi:
                context.ui.print(
                    "  *** {} affiliation(s) skipped — author listed multiple affiliations."
                    " These need follow-up. ***".format(skipped_multi)
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


class PaperNormalizationStep(Step):
    """Print a paper header and queue name/affiliation resolution steps for it."""

    def __init__(
        self,
        paper: ParsedPaper,
        index: int,
        total: int,
        tracks: dict[int, str],
    ) -> None:
        self._paper = paper
        self._index = index
        self._total = total
        self._tracks = tracks

    def execute(self, context: RunContext) -> list[Step]:
        ui = context.ui
        config = context.config_doc.config
        state = context.state
        paper = self._paper

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
            else:
                canonical_affil = find_canonical_affiliation(
                    config, canonical_name, author.affiliations
                )
                if canonical_affil is not None:
                    status = "→ {}".format(canonical_affil)
                else:
                    key = affiliation_key(canonical_name, author.affiliations)
                    status = (
                        "(affiliation skipped)"
                        if key in state.skipped_affiliations
                        else "(affiliation unresolved)"
                    )
            ui.print("    {}  {}".format(name_display, status))
        ui.print()

        # Name resolution steps first; affiliation steps computed after names resolve.
        name_steps: list[Step] = []
        for author in paper.authors:
            if find_canonical_name(config, author.name) is not None:
                continue
            if author.name in state.skipped_names and not context.review_skipped:
                continue
            name_steps.append(ResolveNameStep(author.name))

        return name_steps + [ResolveAffilsForPaperStep(paper)]


class ResolveAffilsForPaperStep(Step):
    """Compute and queue affiliation resolution steps for one paper."""

    def __init__(self, paper: ParsedPaper) -> None:
        self._paper = paper

    def execute(self, context: RunContext) -> list[Step]:
        config = context.config_doc.config
        state = context.state
        steps: list[Step] = []
        for author in self._paper.authors:
            canonical_name = find_canonical_name(config, author.name)
            if canonical_name is None:
                continue
            if (
                find_canonical_affiliation(
                    config, canonical_name, author.affiliations
                )
                is not None
            ):
                continue
            key = affiliation_key(canonical_name, author.affiliations)
            if key in state.skipped_affiliations and not context.review_skipped:
                continue
            steps.append(ResolveAffiliationStep(canonical_name, author.affiliations, key))
        return steps


class ResolveNameStep(Step):
    """Prompt the user to resolve one unrecognized author name."""

    def __init__(self, raw_name: str) -> None:
        self._raw_name = raw_name

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
            canonical = next(
                (c for c in existing if c.casefold() == typed_cf), None
            )

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
                    summary="Mapped '{}' as alias for '{}'".format(
                        raw_name, canonical
                    ),
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
    ) -> None:
        self._author_name = author_name
        self._affiliations = affiliations
        self._key = key

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

        # Auto-skip authors with multiple affiliations — can't pick one unambiguously.
        if len(affiliations) > 1:
            if key not in state.skipped_multi_affiliations:
                state.skipped_multi_affiliations.append(key)
                save_state(state, path_state)
            return []

        ui.print()
        ui.print("  Affiliation for '{}'".format(author_name))
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
        SKIP = "Skip for now"
        QUIT = "Quit"

        choices: list[UIChoice] = []
        if USE_AS_CANONICAL:
            choices.append(UIChoice(title=USE_AS_CANONICAL, shortcut_key="u"))
        choices += [
            UIChoice(title=EDIT_AS_CANONICAL, shortcut_key="e"),
            UIChoice(title=ALIAS_TO_ANOTHER, shortcut_key="a"),
            UIChoice(title=SKIP, shortcut_key="s"),
        ]
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

        if action == USE_AS_CANONICAL:
            canonical = single_institution  # type: ignore[assignment]
            internal = _ask_internal(ui, canonical)
            try:
                config_doc.add_affiliation(canonical, [], internal=internal, papers=context.papers)
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
            match_rule = _ask_match_fields(ui, author_name, affiliations)
            if match_rule is None:
                raise QuitRequested()
            internal = _ask_internal(ui, canonical)
            try:
                config_doc.add_affiliation(canonical, [match_rule], internal=internal, papers=context.papers)
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
            typed = ui.autocomplete(
                "  Canonical affiliation:", existing_canonicals
            )
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

            match_rule = _ask_match_fields(ui, author_name, affiliations)
            if match_rule is None:
                raise QuitRequested()
            try:
                config_doc.add_affiliation_match_rule(canonical, match_rule, papers=context.papers)
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
                )
            )

        if key in state.skipped_affiliations:
            state.skipped_affiliations.remove(key)
        save_state(state, path_state)
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ask_match_fields(
    ui: UI,
    author_name: str,
    affiliations: list[Affiliation],
) -> AffiliationMatchRule | None:
    """Ask the user which fields should define the match rule."""
    INSTITUTION = "Institution only"
    INSTITUTION_DSL = "Institution + DSL"
    INSTITUTION_DSL_AUTHOR = "Institution + DSL + author name"

    result = ui.select(
        "  Match on which fields?",
        [
            UIChoice(title=INSTITUTION, shortcut_key="i"),
            UIChoice(title=INSTITUTION_DSL, shortcut_key="d"),
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

    # INSTITUTION_DSL_AUTHOR
    return AffiliationMatchRule(
        name=author_name,
        affiliations=[
            AffiliationPatternItem(institution=a.institution, dsl=a.dsl or None)
            for a in affiliations
            if a.institution
        ],
    )


def _ask_internal(ui: UI, canonical: str) -> bool:
    """Ask whether a newly-created canonical affiliation is internal or external."""
    result = ui.select(
        "  Is '{}' internal or external?".format(canonical),
        [
            UIChoice(title="Internal", shortcut_key="i"),
            UIChoice(title="External", shortcut_key="e"),
        ],
    )
    if result is None:
        raise QuitRequested()
    return result == "Internal"


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
        key = affiliation_key(canonical_name, author.affiliations)
        if find_canonical_affiliation(config, canonical_name, author.affiliations) is None:
            if key in state.skipped_multi_affiliations:
                continue
            if key not in state.skipped_affiliations or context.review_skipped:
                return True
    return False
