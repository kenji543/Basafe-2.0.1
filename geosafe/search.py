"""Normalization helpers for the municipal-scale local search index."""

from __future__ import annotations

import re
import unicodedata


def normalize_search_text(value: str) -> str:
    """Return a punctuation-insensitive, whitespace-normalized search value."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^0-9A-Za-z]+", " ", text.casefold())
    return " ".join(text.split())
