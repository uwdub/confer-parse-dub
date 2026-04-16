"""Affiliation review steps — prompts for include/exclude decisions."""

from collections import defaultdict
from typing import override

from confer_parse_dub.exceptions import QuitRequested
from confer_parse_dub.models.paper import ParsedPaper
from confer_parse_dub.processing.filter import apply_filters
from confer_parse_dub.steps.context import RunContext, Step


class ReviewAffiliationsStep(Step):
    """
    Always-run affiliation review.

    Computes institution and DSL values newly appearing in the filtered papers
    and returns per-item review steps.  A separate ReviewDslSectionStep runs
    after all institution decisions so it can skip DSLs already covered by
    an included institution.
    """

    @override
    def execute(self, context: RunContext) -> list[Step]:
        config = context.config_doc.config
        keywords = [kw for rule in config.query for kw in rule.keywords]
        if not keywords:
            return []

        already_inst = {r.name for r in config.include_institution} | {
            r.name for r in config.exclude_institution
        }
        already_dsl = {r.name for r in config.include_dsl} | {
            r.name for r in config.exclude_dsl
        }

        inst_groups = _group_by_field(context.papers, keywords, "institution")
        dsl_groups = _group_by_field(context.papers, keywords, "dsl")

        new_inst = {k: v for k, v in inst_groups.items() if k not in already_inst}
        new_dsl = {k: v for k, v in dsl_groups.items() if k not in already_dsl}

        kw_display = ", ".join("'{}'".format(k) for k in sorted(set(keywords)))

        context.ui.print("=== Affiliation Review ===")

        if not new_inst and not new_dsl:
            inst_count = len(already_inst)
            dsl_count = len(already_dsl)
            context.ui.print(
                "{} institution(s) and {} DSL value(s) reviewed — nothing new.".format(
                    inst_count, dsl_count
                )
            )
            context.ui.print()
            return []

        context.ui.print("Reviewing new matches for {}.".format(kw_display))
        context.ui.print("Default is YES — only say No for false positives.")
        context.ui.print()

        steps: list[Step] = []

        if new_inst:
            context.ui.print("Institutions:")
            context.ui.print()
            for name, papers in sorted(new_inst.items(), key=lambda x: -len(x[1])):
                steps.append(ReviewInstitutionStep(name, papers))

        # DSL section runs after all institution steps so it can filter
        # DSL items already covered by newly-included institutions.
        if new_dsl:
            steps.append(ReviewDslSectionStep(new_dsl))

        steps.append(ApplyFiltersStep())
        return steps


class ReviewInstitutionStep(Step):
    """Prompt the user to include or exclude one institution."""

    def __init__(self, name: str, papers: list[ParsedPaper]) -> None:
        self._name: str = name
        self._papers: list[ParsedPaper] = papers

    @override
    def execute(self, context: RunContext) -> list[Step]:
        ui = context.ui
        _print_review_item(ui, "Institution", self._name, self._papers)

        include = ui.confirm(
            "Include papers from '{}'?".format(self._name), default=True
        )
        if include is None:
            raise QuitRequested()

        if include:
            context.config_doc.add_include_institution(self._name)
        else:
            context.config_doc.add_exclude_institution(self._name)
            ui.print("  '{}' added to exclude_institution.".format(self._name))
        ui.print()
        return []


class ReviewDslSectionStep(Step):
    """
    Print the DSL section header and return per-DSL review steps.

    Executes after all institution decisions have been recorded so it can
    skip any DSL values whose papers are already covered by an included
    institution.
    """

    def __init__(self, initial_dsl_groups: dict[str, list[ParsedPaper]]) -> None:
        self._dsl_groups: dict[str, list[ParsedPaper]] = initial_dsl_groups

    @override
    def execute(self, context: RunContext) -> list[Step]:
        config = context.config_doc.config
        keywords = [kw for rule in config.query for kw in rule.keywords]
        inst_covered_ids = _papers_included_by_institution(
            context.papers, keywords, config
        )

        remaining: dict[str, list[ParsedPaper]] = {
            name: [p for p in papers if p.id not in inst_covered_ids]
            for name, papers in self._dsl_groups.items()
        }
        remaining = {k: v for k, v in remaining.items() if v}

        if not remaining:
            return []

        context.ui.print("DSL values:")
        context.ui.print()

        steps: list[Step] = []
        for name, papers in sorted(remaining.items(), key=lambda x: -len(x[1])):
            institutions = sorted(
                {
                    affil.institution
                    for paper in papers
                    for author in paper.authors
                    for affil in author.affiliations
                    if affil.dsl == name and affil.institution
                }
            )
            steps.append(ReviewDslStep(name, papers, institutions))
        return steps


class ReviewDslStep(Step):
    """Prompt the user to include or exclude one DSL value."""

    def __init__(
        self, name: str, papers: list[ParsedPaper], institutions: list[str]
    ) -> None:
        self._name: str = name
        self._papers: list[ParsedPaper] = papers
        self._institutions: list[str] = institutions

    @override
    def execute(self, context: RunContext) -> list[Step]:
        ui = context.ui
        _print_review_item(
            ui, "DSL", self._name, self._papers, extra_lines=self._institutions
        )

        include = ui.confirm(
            "Include papers with DSL '{}'?".format(self._name), default=True
        )
        if include is None:
            raise QuitRequested()

        if include:
            context.config_doc.add_include_dsl(self._name)
        else:
            context.config_doc.add_exclude_dsl(self._name)
            ui.print("  '{}' added to exclude_dsl.".format(self._name))
        ui.print()
        return []


class ApplyFiltersStep(Step):
    """Apply all configured filters to context.papers."""

    @override
    def execute(self, context: RunContext) -> list[Step]:
        context.papers = apply_filters(context.config_doc.config, context.papers)
        context.ui.print(
            "{} papers after affiliation review.".format(len(context.papers))
        )
        context.ui.print()
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_review_item(
    ui: object,
    kind: str,
    name: str,
    papers: list[ParsedPaper],
    extra_lines: list[str] | None = None,
) -> None:
    from confer_parse_dub.steps.context import UI

    assert isinstance(ui, UI)
    ui.print("--- {} ---".format(kind))
    ui.print("  '{}'  ({} paper(s))".format(name, len(papers)))
    if extra_lines:
        for line in extra_lines:
            ui.print("  Institution: '{}'".format(line))
    for paper in papers[:3]:
        ui.print("    - {}".format(paper.title[:72]))
    if len(papers) > 3:
        ui.print("    ... and {} more.".format(len(papers) - 3))
    ui.print()


def _papers_included_by_institution(
    papers: list[ParsedPaper],
    keywords: list[str],
    config: object,
) -> set[int]:
    """Return IDs of papers already covered by a keyword-matching included institution."""
    from confer_parse_dub.models.config import Config

    assert isinstance(config, Config)
    casefold_keywords = [k.casefold() for k in keywords]
    included_institutions = {r.name.casefold() for r in config.include_institution}
    result: set[int] = set()
    for paper in papers:
        for author in paper.authors:
            for affil in author.affiliations:
                if (
                    any(kw in affil.institution.casefold() for kw in casefold_keywords)
                    and affil.institution.casefold() in included_institutions
                ):
                    result.add(paper.id)
    return result


def _group_by_field(
    papers: list[ParsedPaper],
    keywords: list[str],
    field: str,
) -> dict[str, list[ParsedPaper]]:
    """Return {value: [papers]} for each affiliation field value that contains a keyword."""
    casefold_keywords = [k.casefold() for k in keywords]
    groups: dict[str, list[ParsedPaper]] = defaultdict(list)
    for paper in papers:
        seen: set[str] = set()
        for author in paper.authors:
            for affil in author.affiliations:
                value = getattr(affil, field, "")
                if not value:
                    continue
                value_cf = value.casefold()
                if (
                    any(kw in value_cf for kw in casefold_keywords)
                    and value not in seen
                ):
                    groups[value].append(paper)
                    seen.add(value)
    return dict(groups)
