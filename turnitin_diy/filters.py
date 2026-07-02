"""Score filters modeled on Turnitin's "exclude quotes" and "exclude
bibliography" options: matched text inside quotation marks, or after a
references-section heading, is excluded from the similarity score."""
from __future__ import annotations

import re

QUOTE_CHAR_RE = re.compile(r'["“”«»]')
OPENERS = {'“', '«'}
CLOSERS = {'”': '“', '»': '«'}

BIB_HEADING_RE = re.compile(
    r"^[ \t]*(references|bibliography|works cited|reference list|literature cited"
    r"|literatura|popis literature)[ \t]*:?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def quote_ranges(text: str) -> list[tuple[int, int]]:
    """Char ranges of quoted passages. Straight quotes toggle open/close;
    curly quotes and guillemets pair by kind. An unclosed opener is ignored
    rather than excluding the rest of the document."""
    ranges: list[tuple[int, int]] = []
    open_char: str | None = None
    open_pos = 0
    for m in QUOTE_CHAR_RE.finditer(text):
        ch = m.group()
        if ch == '"':
            if open_char is None:
                open_char, open_pos = ch, m.start()
            elif open_char == '"':
                ranges.append((open_pos, m.end()))
                open_char = None
        elif ch in OPENERS:
            if open_char is None:
                open_char, open_pos = ch, m.start()
        elif ch in CLOSERS:
            if open_char == CLOSERS[ch]:
                ranges.append((open_pos, m.end()))
                open_char = None
    return ranges


def bibliography_range(text: str) -> tuple[int, int] | None:
    """Char range from the last references/bibliography heading to the end."""
    headings = list(BIB_HEADING_RE.finditer(text))
    if not headings:
        return None
    return (headings[-1].start(), len(text))


def excluded_char_ranges(text: str, exclude_quotes: bool, exclude_bibliography: bool) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    if exclude_quotes:
        ranges.extend(quote_ranges(text))
    if exclude_bibliography:
        bib = bibliography_range(text)
        if bib:
            ranges.append(bib)
    return ranges


def excluded_word_indices(word_spans: list[tuple[int, int]], ranges: list[tuple[int, int]]) -> set[int]:
    """Indices of words whose char span overlaps any excluded range."""
    if not ranges:
        return set()
    excluded: set[int] = set()
    for i, (ws, we) in enumerate(word_spans):
        for rs, re_ in ranges:
            if ws < re_ and we > rs:
                excluded.add(i)
                break
    return excluded


def describe_filters(exclude_quotes: bool, exclude_bibliography: bool) -> str | None:
    active = []
    if exclude_quotes:
        active.append("quoted material excluded")
    if exclude_bibliography:
        active.append("bibliography/references section excluded")
    return "; ".join(active) if active else None
