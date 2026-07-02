"""Compare a target document against a corpus of reference sources.

Mirrors the shape of a Turnitin Similarity Report: an overall overlap
percentage plus a list of matched passages, each attributed to the source it
overlaps with.
"""
from __future__ import annotations

from dataclasses import dataclass

from .filters import excluded_char_ranges, excluded_word_indices
from .shingle import Shingle, shingle_hashes, tokenize, tokenize_with_spans, winnow


@dataclass
class Source:
    id: str
    fingerprint: dict[int, list[tuple[int, int]]]  # hash -> [(start_word, end_word), ...]


@dataclass
class Match:
    source_id: str
    target_start: int
    target_end: int
    source_start: int
    source_end: int


def build_source(source_id: str, text: str, k: int = 8, window: int = 4) -> Source:
    words = tokenize(text)
    shingles = winnow(shingle_hashes(words, k), window)
    fingerprint: dict[int, list[tuple[int, int]]] = {}
    for s in shingles:
        fingerprint.setdefault(s.hash, []).append((s.start_word, s.end_word))
    return Source(id=source_id, fingerprint=fingerprint)


def find_matches(
    target_text: str,
    sources: list[Source],
    k: int = 8,
    window: int = 4,
    min_run: int = 8,
    exclude_quotes: bool = False,
    exclude_bibliography: bool = False,
) -> tuple[list[str], list[Match], float]:
    """Returns (target_words, merged_matches, overlap_fraction).

    With exclude_quotes/exclude_bibliography set (mirroring Turnitin's score
    filters), words inside quotation marks or after a references heading
    don't count toward matches or the score; a match must still contain
    min_run non-excluded words to be reported."""
    words, word_spans = tokenize_with_spans(target_text)
    excluded: set[int] = set()
    if exclude_quotes or exclude_bibliography:
        ranges = excluded_char_ranges(target_text, exclude_quotes, exclude_bibliography)
        excluded = excluded_word_indices(word_spans, ranges)

    shingles: list[Shingle] = winnow(shingle_hashes(words, k), window)

    raw: list[tuple[int, int, str, int, int]] = []
    for s in shingles:
        for src in sources:
            spans = src.fingerprint.get(s.hash)
            if not spans:
                continue
            for ss, se in spans:
                raw.append((s.start_word, s.end_word, src.id, ss, se))
    raw.sort(key=lambda m: (m[2], m[0]))

    merged: list[Match] = []
    for ts, te, sid, ss, se in raw:
        if merged and merged[-1].source_id == sid and ts <= merged[-1].target_end:
            last = merged[-1]
            last.target_end = max(last.target_end, te)
            last.source_end = max(last.source_end, se)
        else:
            merged.append(Match(source_id=sid, target_start=ts, target_end=te, source_start=ss, source_end=se))

    def counted_len(m: Match) -> int:
        return sum(1 for i in range(m.target_start, min(m.target_end, len(words))) if i not in excluded)

    merged = [m for m in merged if counted_len(m) >= min_run]

    matched_flags = [False] * len(words)
    for m in merged:
        for i in range(m.target_start, min(m.target_end, len(words))):
            if i not in excluded:
                matched_flags[i] = True

    total = len(words) or 1
    overlap = sum(matched_flags) / total

    merged.sort(key=lambda m: m.target_start)
    return words, merged, overlap


def summarize_by_source(n_words: int, matches: list[Match]) -> list[tuple[str, float]]:
    """Per-source overlap fractions (like Turnitin's source list), computed
    from distinct matched word positions per source, sorted highest first."""
    per_source: dict[str, set[int]] = {}
    for m in matches:
        per_source.setdefault(m.source_id, set()).update(range(m.target_start, min(m.target_end, n_words)))
    total = max(n_words, 1)
    return sorted(((sid, len(ix) / total) for sid, ix in per_source.items()), key=lambda t: -t[1])
