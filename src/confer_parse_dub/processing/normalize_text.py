"""Utilities for normalizing text content."""


def normalize_text(text: str) -> str:
    """Normalize whitespace and common Unicode characters in text."""
    while "  " in text:
        text = text.replace("  ", " ")

    text = text.replace("\u2013", "-")
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')

    text = text.strip()

    return text
