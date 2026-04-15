"""Output steps — validation and YAML writing."""

import pathlib
from typing import override

from confer_parse_dub.io.output import check_resolved, write_output
from confer_parse_dub.processing.normalize_titles import normalize_titles
from confer_parse_dub.processing.sort import sort_papers
from confer_parse_dub.steps.context import RunContext, Step


class CheckOutputStep(Step):
    """Validate all papers are resolved; if so, proceed to write output."""

    @override
    def execute(self, context: RunContext) -> list[Step]:
        problems = check_resolved(context.papers, context.state)
        if problems:
            context.ui.print(
                "=== Cannot generate output: {} unresolved item(s) ===".format(
                    len(problems)
                )
            )
            for problem in problems[:20]:
                context.ui.print("  - {}".format(problem))
            if len(problems) > 20:
                context.ui.print("  ... and {} more.".format(len(problems) - 20))
            context.ui.print()
            context.ui.print(
                "Run again to continue, or add --review-skipped to revisit skipped items."
            )
            return []

        return [WriteOutputStep()]


class WriteOutputStep(Step):
    """Normalize titles, sort papers, and write the output YAML."""

    @override
    def execute(self, context: RunContext) -> list[Step]:
        config = context.config_doc.config
        papers = normalize_titles(context.papers)
        papers = sort_papers(papers)

        path_output = pathlib.Path(config.file_output)
        path_output.parent.mkdir(parents=True, exist_ok=True)
        write_output(papers, path_output)

        total = len(papers)
        best = sum(1 for p in papers if p.bestpaper)
        hm = sum(1 for p in papers if p.honorablemention)

        internal_canonicals = {e.canonical for e in config.internal_affiliations}
        internal_seen: set[str] = set()
        for paper in papers:
            for author in paper.authors:
                for affil in author.canonical_affiliations:
                    if affil in internal_canonicals:
                        internal_seen.add(affil)

        context.ui.print("=== Output ===")
        context.ui.print("Wrote {} papers to {}.".format(total, path_output))
        context.ui.print("  {} best paper award".format(best))
        context.ui.print("  {} best paper honorable mention".format(hm))
        context.ui.print()
        context.ui.print(
            "  {} internal affiliation(s) represented:".format(len(internal_seen))
        )
        for affil in sorted(internal_seen):
            context.ui.print("    - {}".format(affil))
        return []
