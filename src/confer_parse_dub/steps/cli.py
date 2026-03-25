"""Command-line implementation of UI using questionary."""

import questionary

from confer_parse_dub.steps.context import UI, UIChoice


class CliUI(UI):
    def select(self, prompt: str, choices: list[UIChoice]) -> str | None:
        use_shortcuts = any(c.shortcut_key for c in choices)
        q_choices = [
            questionary.Choice(
                title=c.title,
                value=c.value if c.value is not None else c.title,
                shortcut_key=c.shortcut_key,
            )
            for c in choices
        ]
        return questionary.select(
            prompt, choices=q_choices, use_shortcuts=use_shortcuts
        ).ask()

    def confirm(self, prompt: str, default: bool = True) -> bool | None:
        return questionary.confirm(prompt, default=default).ask()

    def text(self, prompt: str, default: str = "") -> str | None:
        return questionary.text(prompt, default=default).ask()

    def autocomplete(self, prompt: str, choices: list[str]) -> str | None:
        return questionary.autocomplete(
            prompt, choices=choices, match_middle=True
        ).ask()

    def checkbox(self, prompt: str, choices: list[UIChoice]) -> list[str] | None:
        q_choices = [
            questionary.Choice(
                title=c.title,
                value=c.value if c.value is not None else c.title,
                checked=c.checked,
            )
            for c in choices
        ]
        return questionary.checkbox(prompt, choices=q_choices).ask()

    def print(self, message: str = "") -> None:
        print(message)
