"""Top-level pipeline steps: load papers, filter summary, apply mappings."""

from typing import override

from confer_parse_dub.config_document import validate_config
from confer_parse_dub.io.parse import parse_sigchi_program
from confer_parse_dub.processing.normalize_affiliations import find_canonical_affiliation
from confer_parse_dub.processing.normalize_names import find_canonical_name
from confer_parse_dub.steps.context import RunContext, Step


class LoadPapersStep(Step):
    """
    Parse the conference JSON and kick off the full pipeline.

    Returns the standard sequence of pipeline steps so the runner executes
    them in order: query → affiliations → filter summary → normalize → output.
    """

    def __init__(self, label: str, config_path: str) -> None:
        self._label: str = label
        self._config_path: str = config_path

    @override
    def execute(self, context: RunContext) -> list[Step]:
        from confer_parse_dub.steps.affiliations import ReviewAffiliationsStep
        from confer_parse_dub.steps.normalize import NormalizePapersStep, ReviewSplitsStep
        from confer_parse_dub.steps.output import CheckOutputStep
        from confer_parse_dub.steps.query import ReviewQueryStep

        ui = context.ui
        ui.print("=== Load ===")
        ui.print("{} — {}".format(self._label, self._config_path))
        ui.print("Source: {}".format(context.config_doc.config.file_input))

        papers = parse_sigchi_program(context.config_doc.config)
        track_count = len({p.trackId for p in papers})
        ui.print(
            "Loaded {} items across {} track(s).".format(len(papers), track_count)
        )

        context.papers = papers
        context.total_loaded = len(papers)

        validate_config(context.config_doc.config, papers)

        return [
            ReviewQueryStep(),
            ReviewAffiliationsStep(),
            FilterSummaryStep(),
            ReviewSplitsStep(),
            NormalizePapersStep(),
            CheckOutputStep(),
        ]


class FilterSummaryStep(Step):
    """Print a summary of active filter rules and the matched paper count."""

    @override
    def execute(self, context: RunContext) -> list[Step]:
        ui = context.ui
        config = context.config_doc.config

        keywords = sorted({kw for r in config.query for kw in r.keywords})
        track_count = len({t.id for r in config.query for t in r.tracks})

        ui.print("=== Filter ===")
        if keywords:
            ui.print(
                "Keywords: {}".format(
                    ", ".join("'{}'".format(k) for k in keywords)
                )
            )
        if track_count:
            ui.print("Tracks: {}".format(track_count))
        if config.include_institution:
            ui.print(
                "Institutions included: {}".format(len(config.include_institution))
            )
        if config.exclude_institution:
            ui.print(
                "Institutions excluded: {}".format(len(config.exclude_institution))
            )
        if config.include_dsl:
            ui.print("DSL values included: {}".format(len(config.include_dsl)))
        if config.exclude_dsl:
            ui.print("DSL values excluded: {}".format(len(config.exclude_dsl)))
        if config.include_paper:
            ui.print(
                "Papers force-included: {}".format(len(config.include_paper))
            )
        if config.exclude_paper:
            ui.print(
                "Papers force-excluded: {}".format(len(config.exclude_paper))
            )
        ui.print(
            "Matched {} of {} items.".format(
                len(context.papers), context.total_loaded
            )
        )
        ui.print()
        return []


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
