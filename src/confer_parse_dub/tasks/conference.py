"""
Tasks for managing conferences.

Each active conference gets its own subcollection:
  invoke <name>    Run the full interactive pipeline (default shortcut).

Everything else is accessible through the interactive manager:
  invoke conferences
"""

import pathlib
from typing import Callable, cast

import questionary
from confer_parse_dub_paths import PATH_DATA
from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

from confer_parse_dub.browser_companion import BrowserCompanion
from confer_parse_dub.config_document import ConfigDocument
from confer_parse_dub.io.conferences_io import load_conferences, save_conferences
from confer_parse_dub.io.state_io import load_state
from confer_parse_dub.io.undo import undo_last_decision
from confer_parse_dub.models.conference import ConferenceEntry
from confer_parse_dub.models.state import ProcessingState
from confer_parse_dub.steps.cli import CliUI
from confer_parse_dub.steps.context import RunContext
from confer_parse_dub.steps.pipeline import LoadPapersStep
from confer_parse_dub.steps.runner import run_steps

_CONFIG_TEMPLATE = """\
version: 'v1'
file_input: '{file_input}'
file_output: '{file_output}'

query: []

include_institution: []
exclude_institution: []

include_paper: []
exclude_paper: []

names: []

internal_affiliations: []
external_affiliations: []
"""


def _conf_label(conf: ConferenceEntry) -> str:
    """Choice label for a conference in a select menu."""
    return "{} ({})".format(conf.label, conf.name)


def _load_states(
    conferences: list[ConferenceEntry],
) -> dict[str, ProcessingState]:
    """Load the state file for every conference that has one."""
    states: dict[str, ProcessingState] = {}
    for conf in conferences:
        path_state = pathlib.Path(conf.config).parent / "state.json"
        if path_state.exists():
            states[conf.name] = load_state(path_state)
    return states


# ---------------------------------------------------------------------------
# Per-conference collection  (run only — the shortcut)
# ---------------------------------------------------------------------------


def get_collection_for_conference(conf: ConferenceEntry) -> Collection:
    """Return an invoke Collection whose default task runs the pipeline."""

    @task(name="run")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_run(
        _context: Context,
        review_skipped: bool = False,
        no_browser: bool = False,
    ) -> None:
        """
        Run the full interactive pipeline for this conference.

        Parses, filters, and interactively normalizes names and affiliations.
        Generates output only when everything is resolved.

        Args:
            review_skipped: Re-prompt for items that were previously skipped.
            no_browser: Disable the browser companion window.
        """
        run_pipeline(conf, review_skipped=review_skipped, browser=not no_browser)

    task_run.__doc__ = "Run analysis for {}.".format(conf.label)

    col = Collection(conf.name)
    col.add_task(
        cast(Task[Callable[..., None]], task_run),
        name="run",
        default=True,
    )
    return col


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


def run_pipeline(
    conf: ConferenceEntry,
    review_skipped: bool = False,
    browser: bool = True,
) -> None:
    """Execute the full processing pipeline for a conference."""
    path_config = pathlib.Path(conf.config)
    path_state = path_config.parent / "state.json"

    if not path_config.exists():
        print("Error: config file not found: {}".format(path_config))
        print("Use 'invoke conferences' to configure a new conference.")
        return

    config_doc = ConfigDocument(path_config)
    state = load_state(path_state)
    companion = BrowserCompanion() if browser else None

    context = RunContext(
        config_doc=config_doc,
        state=state,
        path_state=path_state,
        ui=CliUI(),
        review_skipped=review_skipped,
        browser=companion,
    )

    try:
        completed = run_steps([LoadPapersStep(conf.label, str(path_config))], context)
    finally:
        if companion is not None:
            companion.close()

    if not completed:
        print(
            (
                "\n"
                + "Stopped. Progress has been saved.\n"
                + "Run 'invoke {}' again to continue, "
                + "or use --review-skipped to revisit skipped items."
            ).format(conf.name)
        )


# ---------------------------------------------------------------------------
# Conference management actions (used by the conferences hub)
# ---------------------------------------------------------------------------


def _action_toggle_complete(
    conferences: list[ConferenceEntry],
    mark_complete: bool,
) -> None:
    """Mark an active conference complete, or reactivate a completed one."""
    candidates = [c for c in conferences if c.complete != mark_complete]

    if not candidates:
        if mark_complete:
            print("No active conferences to mark as complete.")
        else:
            print("No completed conferences to reactivate.")
        return

    question = (
        "Which conference is complete?"
        if mark_complete
        else "Which conference do you want to reactivate?"
    )
    choices: list[str] = [_conf_label(c) for c in candidates] + ["Cancel"]
    choice = questionary.select(question, choices=choices).ask()

    if not choice or choice == "Cancel":
        return

    selected = next(c for c in candidates if _conf_label(c) == choice)

    if mark_complete:
        confirm_msg = "Mark '{}' as complete?".format(selected.label)
        success_msg = "'{}' marked as complete.".format(selected.label)
    else:
        confirm_msg = "Reactivate '{}'? It will reappear in the task list.".format(
            selected.label
        )
        success_msg = "'{}' reactivated.".format(selected.label)

    if not questionary.confirm(confirm_msg, default=True).ask():
        return

    for conf in conferences:
        if conf.name == selected.name:
            conf.complete = mark_complete
            break

    save_conferences(conferences)
    print(success_msg)


def _action_undo(
    conferences: list[ConferenceEntry],
    states: dict[str, ProcessingState],
) -> None:
    """Interactively undo recent decisions for a conference."""
    with_history = [
        (conf, states[conf.name], pathlib.Path(conf.config).parent / "state.json")
        for conf in conferences
        if conf.name in states and states[conf.name].history
    ]

    if not with_history:
        print("No decision history found for any conference.")
        return

    if len(with_history) == 1:
        conf, state, path_state = with_history[0]
    else:
        choices: list[str] = [
            "{} ({} decision(s))".format(c.label, len(s.history))
            for c, s, _ in with_history
        ] + ["Cancel"]
        choice = questionary.select("Which conference?", choices=choices).ask()
        if not choice or choice == "Cancel":
            return
        conf, state, path_state = with_history[choices.index(choice)]

    config_doc = ConfigDocument(pathlib.Path(conf.config))

    undo_choices: list[str] = []
    for i, decision in enumerate(reversed(state.history)):
        steps = i + 1
        if steps == 1:
            undo_choices.append("Undo 1 step: {}".format(decision.summary))
        else:
            undo_choices.append(
                "Undo {} steps (back to: {})".format(steps, decision.summary)
            )
    undo_choices.append("Cancel")

    print()
    choice = questionary.select(
        "How far back do you want to undo? ({})".format(conf.label),
        choices=undo_choices,
    ).ask()

    if not choice or choice == "Cancel":
        return

    steps_to_undo = undo_choices.index(choice) + 1

    if not questionary.confirm(
        "Undo {} decision(s)?".format(steps_to_undo), default=True
    ).ask():
        return

    for _ in range(steps_to_undo):
        decision = undo_last_decision(config_doc, state, path_state)
        if decision:
            print("  Undone: {}".format(decision.summary))

    print()
    print("{} decision(s) remaining in history.".format(len(state.history)))


def _action_configure(conferences: list[ConferenceEntry]) -> None:
    """Interactively set up a new conference."""
    existing_names = {c.name for c in conferences}

    name = questionary.text(
        "Short name (e.g., chi2026, cscw2025):",
        validate=lambda v: (
            True
            if v and v.isidentifier() and v not in existing_names
            else "Must be a valid identifier and not already in use."
        ),
    ).ask()
    if not name:
        return

    label = questionary.text(
        "Human-readable label (e.g., CHI 2026):",
        validate=lambda v: bool(v.strip()),
    ).ask()
    if not label:
        return

    default_input = "{}_program.json".format(name.upper())
    input_file = questionary.text(
        "Input JSON file name:",
        default=default_input,
    ).ask()
    if not input_file:
        return

    dir_path = PATH_DATA / name
    path_config = dir_path / "config.yml"
    path_input = dir_path / input_file
    path_output = dir_path / "{}papers.yml".format(name)

    print()
    print("Will create:")
    print("  Directory : {}".format(dir_path))
    print("  Config    : {}".format(path_config))
    print("  Input JSON: {}".format(path_input))
    print("  Output    : {}".format(path_output))
    print()

    if not questionary.confirm("Proceed?", default=True).ask():
        return

    dir_path.mkdir(parents=True, exist_ok=True)
    config_content = _CONFIG_TEMPLATE.format(
        file_input=str(path_input).replace("\\", "/"),
        file_output=str(path_output).replace("\\", "/"),
    )
    with open(path_config, "w", encoding="utf-8") as f:
        _ = f.write(config_content)

    conferences.append(
        ConferenceEntry(
            name=name,
            label=label,
            config=str(path_config).replace("\\", "/"),
        )
    )
    save_conferences(conferences)

    print()
    print("'{}' configured.".format(label))
    print("  Place the input JSON at: {}".format(path_input))
    print("  Edit {} to add include/exclude rules.".format(path_config))
    print("  Then run: invoke {}".format(name))


# ---------------------------------------------------------------------------
# Conferences hub task
# ---------------------------------------------------------------------------


def get_task_conferences() -> Task[Callable[[Context], None]]:
    @task(name="conferences")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_conferences(_context: Context) -> None:
        """
        Manage conferences: list, configure, complete, reactivate, and more.
        """
        if not load_conferences():
            print("No conferences configured yet.")
            conferences: list[ConferenceEntry] = []
            _action_configure(conferences)
            return

        while True:
            # Reload from disk at the top of every iteration so the display
            # always reflects changes made in the previous action.
            conferences = load_conferences()
            active = [c for c in conferences if not c.complete]
            complete = [c for c in conferences if c.complete]

            # Load all state files once — used for both display and menu choices.
            states = _load_states(conferences)

            print()
            if active:
                print("Active:")
                for conf in active:
                    state = states.get(conf.name)
                    skipped_note = ""
                    if state:
                        pending = len(state.skipped_names) + len(
                            state.skipped_affiliations
                        )
                        if pending:
                            skipped_note = "  ({} skipped)".format(pending)
                    print("  {:24s}  {}{}".format(conf.label, conf.name, skipped_note))

            if complete:
                print()
                print("Complete:")
                for conf in complete:
                    print("  {:24s}  {}".format(conf.label, conf.name))

            has_history = any(s.history for s in states.values())

            actions: list[str] = []
            if active:
                actions.append("Mark a conference as complete")
            if complete:
                actions.append("Reactivate a conference")
            if has_history:
                actions.append("Undo a decision")
            actions.append("Configure a new conference")
            actions.append("Done")

            print()
            action = questionary.select(
                "What would you like to do?",
                choices=actions,
            ).ask()

            if action is None or action == "Done":
                break
            elif action == "Mark a conference as complete":
                _action_toggle_complete(conferences, mark_complete=True)
            elif action == "Reactivate a conference":
                _action_toggle_complete(conferences, mark_complete=False)
            elif action == "Undo a decision":
                _action_undo(conferences, states)
            elif action == "Configure a new conference":
                _action_configure(conferences)

    return cast(Task[Callable[[Context], None]], task_conferences)
