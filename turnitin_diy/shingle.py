"""Document fingerprinting via k-word shingling + winnowing.

This is the technique underneath Turnitin-style similarity detection and
MOSS-style code-plagiarism detection: break text into overlapping k-word
"shingles", hash each one, then keep only a representative subset of hashes
(winnowing) so two documents can be compared by fingerprint overlap instead
of a full-text diff. Winnowing guarantees that any shared run of at least
`window` shingles produces at least one shared fingerprint.

Reference: Schleimer, Wilkerson & Aiken, "Winnowing: Local Algorithms for
Document Fingerprinting" (SIGMOD 2003).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

WORD_RE = re.compile(r"[^\W\d_]+|\d+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lowercase word/number tokens, punctuation and whitespace stripped."""
    return WORD_RE.findall(text.lower())


def tokenize_with_spans(text: str) -> tuple[list[str], list[tuple[int, int]]]:
    """Same tokens as tokenize(), plus each token's (start, end) char offsets,
    so word indices can be mapped back to positions in the original text."""
    words: list[str] = []
    spans: list[tuple[int, int]] = []
    for m in WORD_RE.finditer(text.lower()):
        words.append(m.group())
        spans.append((m.start(), m.end()))
    return words, spans


@dataclass(frozen=True)
class Shingle:
    hash: int
    start_word: int
    end_word: int


def shingle_hashes(words: list[str], k: int = 8) -> list[Shingle]:
    """Hash of every overlapping k-word window, in document order."""
    if len(words) < k:
        return []
    out = []
    for i in range(len(words) - k + 1):
        gram = " ".join(words[i : i + k])
        digest = hashlib.sha1(gram.encode("utf-8")).digest()
        h = int.from_bytes(digest[:8], "big")
        out.append(Shingle(hash=h, start_word=i, end_word=i + k))
    return out


def winnow(shingles: list[Shingle], window: int = 4) -> list[Shingle]:
    """Keep the minimum-hash shingle in every rolling window of `window`
    shingles, deduplicated by position. Shrinks the fingerprint set while
    still guaranteeing detection of any matching run >= window shingles."""
    if not shingles:
        return []
    if len(shingles) <= window:
        return list({s.hash: s for s in shingles}.values())

    selected: dict[int, Shingle] = {}
    last_pos = -1
    for i in range(len(shingles) - window + 1):
        win = shingles[i : i + window]
        m = min(win, key=lambda s: s.hash)
        pos = i + win.index(m)
        if pos != last_pos:
            selected[m.hash] = m
            last_pos = pos
    return list(selected.values())
