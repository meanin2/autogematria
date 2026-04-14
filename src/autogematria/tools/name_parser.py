"""Structured parsing of Jewish name input.

Handles patterns like:
  - "משה" (single name)
  - "משה גינדי" (first + surname)
  - "moshe ben yitzchak" (first + patronymic)
  - "moshe ben yitzchak gindi" (first + patronymic + surname)
  - "moshe ben yitzchak v'miriam gindi" (first + father + mother + surname)
  - "שרה בת אברהם ורבקה" (first + father + mother, Hebrew)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from autogematria.tools.name_variants import contains_hebrew, generate_hebrew_variants


_BEN_PATTERNS = re.compile(
    r"\b(ben|bar|ibn)\b", re.IGNORECASE
)
_BAT_PATTERNS = re.compile(
    r"\b(bat|bas)\b", re.IGNORECASE
)
_AND_PATTERNS = re.compile(
    r"\b(v['\u2019]?|and|u|ve|v)\b", re.IGNORECASE
)

_HEB_BEN = re.compile(r"\bבן\b")
_HEB_BAT = re.compile(r"\bבת\b")
_HEB_AND = re.compile(r"\b[וו](?=\S)")

_PATRONYMIC_MARKERS = {"ben", "bar", "ibn", "bat", "bas"}
_CONNECTOR_WORDS = {"v", "ve", "and", "u", "v'"}


@dataclass(frozen=True)
class ParsedName:
    """Structured representation of a Jewish name."""

    raw_input: str
    first_name: str
    patronymic_type: str | None = None  # "ben" or "bat"
    father_name: str | None = None
    mother_name: str | None = None
    surname: str | None = None
    extra_names: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        parts = [self.first_name]
        if self.patronymic_type and self.father_name:
            parts.append(self.patronymic_type)
            parts.append(self.father_name)
        if self.mother_name:
            conj = "ו" if contains_hebrew(self.first_name) else "v'"
            parts.append(conj + self.mother_name)
        if self.surname:
            parts.append(self.surname)
        return " ".join(parts)

    @property
    def searchable_components(self) -> list[tuple[str, str]]:
        """Return (text, role) pairs for each name component worth searching."""
        parts: list[tuple[str, str]] = [(self.first_name, "first_name")]
        if self.father_name:
            parts.append((self.father_name, "father_name"))
        if self.mother_name:
            parts.append((self.mother_name, "mother_name"))
        if self.surname:
            parts.append((self.surname, "surname"))
        for name in self.extra_names:
            parts.append((name, "extra"))
        return parts

    @property
    def all_name_tokens(self) -> list[str]:
        """All meaningful name tokens (no connectors)."""
        return [text for text, _ in self.searchable_components]

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_input": self.raw_input,
            "first_name": self.first_name,
            "patronymic_type": self.patronymic_type,
            "father_name": self.father_name,
            "mother_name": self.mother_name,
            "surname": self.surname,
            "extra_names": list(self.extra_names),
            "display_name": self.display_name,
            "searchable_components": [
                {"text": t, "role": r} for t, r in self.searchable_components
            ],
        }


def _split_on_and(text: str) -> list[str]:
    """Split on 've/v'/and' connectors, handling both Hebrew and English.

    For Hebrew, only split on a standalone vav prefix before a space-separated word,
    not on vav that's part of a word (like שמעון).
    """
    if contains_hebrew(text):
        parts = re.split(r"\s+ו(?=\S)", text, maxsplit=1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return [parts[0].strip(), parts[1].strip()]
        return [text]
    parts = _AND_PATTERNS.split(text)
    return [p.strip() for p in parts if p.strip() and p.strip().lower() not in _CONNECTOR_WORDS]


def _has_latin_patronymic(text: str) -> bool:
    """Check if text contains a Latin-script patronymic marker like 'ben'."""
    tokens = text.lower().split()
    return any(t.rstrip("'") in ("ben", "bar", "ibn", "bat", "bas") for t in tokens)


def parse_name(raw: str) -> ParsedName:
    """Parse a name string into structured components."""
    raw = raw.strip()
    if not raw:
        return ParsedName(raw_input=raw, first_name="")

    if _has_latin_patronymic(raw):
        return _parse_english_name(raw)
    if contains_hebrew(raw):
        return _parse_hebrew_name(raw)
    return _parse_english_name(raw)


def _parse_hebrew_name(raw: str) -> ParsedName:
    tokens = raw.split()
    if len(tokens) == 1:
        return ParsedName(raw_input=raw, first_name=tokens[0])

    patronymic_type = None
    patron_idx = None
    for i, t in enumerate(tokens):
        if t == "בן":
            patronymic_type = "בן"
            patron_idx = i
            break
        if t == "בת":
            patronymic_type = "בת"
            patron_idx = i
            break

    if patron_idx is None:
        first = tokens[0]
        rest = tokens[1:]
        if len(rest) == 1:
            return ParsedName(raw_input=raw, first_name=first, surname=rest[0])
        if len(rest) >= 2:
            return ParsedName(
                raw_input=raw,
                first_name=first,
                surname=rest[-1],
                extra_names=rest[:-1],
            )
        return ParsedName(raw_input=raw, first_name=first)

    first_name = " ".join(tokens[:patron_idx])
    after_patron = tokens[patron_idx + 1:]

    if not after_patron:
        return ParsedName(
            raw_input=raw,
            first_name=first_name,
            patronymic_type=patronymic_type,
        )

    parent_part = " ".join(after_patron)
    and_parts = _split_on_and(parent_part)

    if len(and_parts) >= 2:
        father_name = and_parts[0].strip()
        remainder = and_parts[1].strip().split()
        mother_name = remainder[0] if remainder else None
        surname = remainder[-1] if len(remainder) > 1 else None
        return ParsedName(
            raw_input=raw,
            first_name=first_name,
            patronymic_type=patronymic_type,
            father_name=father_name,
            mother_name=mother_name,
            surname=surname,
        )

    parent_tokens = after_patron
    if len(parent_tokens) == 1:
        return ParsedName(
            raw_input=raw,
            first_name=first_name,
            patronymic_type=patronymic_type,
            father_name=parent_tokens[0],
        )

    return ParsedName(
        raw_input=raw,
        first_name=first_name,
        patronymic_type=patronymic_type,
        father_name=parent_tokens[0],
        surname=parent_tokens[-1] if len(parent_tokens) > 1 else None,
        extra_names=parent_tokens[1:-1] if len(parent_tokens) > 2 else [],
    )


def _parse_english_name(raw: str) -> ParsedName:
    tokens = raw.split()
    if len(tokens) == 1:
        return ParsedName(raw_input=raw, first_name=tokens[0])

    patronymic_type = None
    patron_idx = None
    for i, t in enumerate(tokens):
        low = t.lower().rstrip("'")
        if low in ("ben", "bar", "ibn"):
            patronymic_type = "ben"
            patron_idx = i
            break
        if low in ("bat", "bas"):
            patronymic_type = "bat"
            patron_idx = i
            break

    if patron_idx is None:
        first = tokens[0]
        rest = tokens[1:]
        if len(rest) == 1:
            return ParsedName(raw_input=raw, first_name=first, surname=rest[0])
        if len(rest) >= 2:
            return ParsedName(
                raw_input=raw,
                first_name=first,
                surname=rest[-1],
                extra_names=rest[:-1],
            )
        return ParsedName(raw_input=raw, first_name=first)

    first_name = " ".join(tokens[:patron_idx])
    after_patron = tokens[patron_idx + 1:]

    if not after_patron:
        return ParsedName(
            raw_input=raw,
            first_name=first_name,
            patronymic_type=patronymic_type,
        )

    parent_part = " ".join(after_patron)
    and_parts = _split_on_and(parent_part)

    if len(and_parts) >= 2:
        father_tokens = and_parts[0].strip().split()
        rest_tokens = and_parts[1].strip().split()
        father_name = father_tokens[0] if father_tokens else None
        surname_from_father = father_tokens[-1] if len(father_tokens) > 1 else None

        mother_name = rest_tokens[0] if rest_tokens else None
        surname = rest_tokens[-1] if len(rest_tokens) > 1 else surname_from_father

        if surname is None and len(tokens) > patron_idx + 3:
            possible_surname = tokens[-1].lower()
            if possible_surname not in _PATRONYMIC_MARKERS and possible_surname not in _CONNECTOR_WORDS:
                surname = tokens[-1]

        return ParsedName(
            raw_input=raw,
            first_name=first_name,
            patronymic_type=patronymic_type,
            father_name=father_name,
            mother_name=mother_name,
            surname=surname,
        )

    parent_tokens = after_patron
    if len(parent_tokens) == 1:
        return ParsedName(
            raw_input=raw,
            first_name=first_name,
            patronymic_type=patronymic_type,
            father_name=parent_tokens[0],
        )

    return ParsedName(
        raw_input=raw,
        first_name=first_name,
        patronymic_type=patronymic_type,
        father_name=parent_tokens[0],
        surname=parent_tokens[-1] if len(parent_tokens) > 1 else None,
        extra_names=parent_tokens[1:-1] if len(parent_tokens) > 2 else [],
    )
