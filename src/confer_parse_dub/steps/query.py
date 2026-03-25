"""Interactive query configuration step."""

from confer_parse_dub.exceptions import QuitRequested
from confer_parse_dub.models.config import Config, QueryRule, TrackRule
from confer_parse_dub.models.paper import ParsedPaper
from confer_parse_dub.processing.filter import apply_filters
from confer_parse_dub.io.parse import count_papers_by_track, parse_tracks
from confer_parse_dub.steps.context import UI, RunContext, Step, UIChoice


class ReviewQueryStep(Step):
    """
    Always-run interactive query configuration.

    If a query already exists, pre-populates the editor and offers Continue
    immediately.  If no query exists, the user must configure at least one
    keyword and one track before continuing.

    Applies query filters to context.papers before returning.
    """

    def execute(self, context: RunContext) -> list[Step]:
        ui = context.ui
        config_doc = context.config_doc

        ui.print("=== Query Configuration ===")
        ui.print()

        tracks = parse_tracks(config_doc.config)
        counts = count_papers_by_track(config_doc.config)

        track_list = sorted(
            [
                (tid, tracks.get(tid, "(unnamed)"), counts.get(tid, 0))
                for tid in tracks
            ],
            key=lambda x: -x[2],
        )
        track_list = [row for row in track_list if row[2] > 0]

        existing = config_doc.config.query[0] if config_doc.config.query else None
        keywords: list[str] = list(existing.keywords) if existing else []
        track_ids: list[int] = [t.id for t in existing.tracks] if existing else []

        changed = False

        while True:
            ui.print()
            _print_query_state(ui, keywords, track_ids, tracks)
            ui.print()

            can_continue = bool(keywords and track_ids)
            choices = [UIChoice(title="Add keyword", shortcut_key="a")]
            if keywords:
                choices.append(UIChoice(title="Remove keyword", shortcut_key="r"))
            choices.append(UIChoice(title="Select tracks", shortcut_key="t"))
            if can_continue:
                choices.append(UIChoice(title="Preview", shortcut_key="p"))
                choices.append(UIChoice(title="Continue", shortcut_key="c"))
            choices.append(UIChoice(title="Quit", shortcut_key="q"))

            action = ui.select("What would you like to do?", choices)
            if action is None or action == "Quit":
                raise QuitRequested()

            if action == "Add keyword":
                raw = ui.text("Keyword:", default="Washington")
                if raw is None:
                    raise QuitRequested()
                kw = raw.strip()
                if kw and kw not in keywords:
                    keywords.append(kw)
                    changed = True

            elif action == "Remove keyword":
                to_remove = ui.select(
                    "Remove which keyword?",
                    [UIChoice(title=k) for k in keywords],
                )
                if to_remove is None:
                    raise QuitRequested()
                keywords.remove(to_remove)
                changed = True

            elif action == "Select tracks":
                track_choices = [
                    UIChoice(
                        title="{} ({} items)".format(name, count),
                        value=str(tid),
                        checked=tid in track_ids,
                    )
                    for tid, name, count in track_list
                ]
                selected = ui.checkbox("Select tracks:", track_choices)
                if selected is None:
                    raise QuitRequested()
                new_ids = [int(v) for v in selected]
                if sorted(new_ids) != sorted(track_ids):
                    changed = True
                track_ids = new_ids

            elif action == "Preview":
                preview = _simulate_filter(context.papers, keywords, track_ids, tracks)
                kw_display = ", ".join("'{}'".format(k) for k in keywords)
                ui.print()
                ui.print(
                    "Preview: {} paper(s) matched for {}.".format(
                        len(preview), kw_display
                    )
                )

            elif action == "Continue":
                break

        new_rule = QueryRule(
            keywords=keywords,
            tracks=[
                TrackRule(id=tid, name=tracks.get(tid, str(tid)))
                for tid in track_ids
            ],
        )

        if changed or not config_doc.config.query:
            config_doc.set_query(new_rule)
            ui.print()
            ui.print("Query saved.")

        context.papers = apply_filters(config_doc.config, context.papers)
        ui.print("Filtered to {} papers.".format(len(context.papers)))
        ui.print()

        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_query_state(
    ui: UI, keywords: list[str], track_ids: list[int], tracks: dict[int, str]
) -> None:
    if keywords:
        ui.print(
            "Keywords: {}".format(", ".join("'{}'".format(k) for k in keywords))
        )
    else:
        ui.print("Keywords: (none)")
    if track_ids:
        track_names = [tracks.get(tid, str(tid)) for tid in sorted(track_ids)]
        ui.print("Tracks:   {}".format(", ".join(track_names)))
    else:
        ui.print("Tracks:   (none selected)")


def _simulate_filter(
    papers: list[ParsedPaper],
    keywords: list[str],
    track_ids: list[int],
    tracks: dict[int, str],
) -> list[ParsedPaper]:
    """Apply a proposed query without modifying any config on disk."""
    temp_config = Config(
        version="v1",
        file_input="",
        file_output="",
        query=[
            QueryRule(
                keywords=keywords,
                tracks=[
                    TrackRule(id=tid, name=tracks.get(tid, str(tid)))
                    for tid in track_ids
                ],
            )
        ],
    )
    return apply_filters(temp_config, papers)
