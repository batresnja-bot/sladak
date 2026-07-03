"""Heuristic, fully transparent writing-pattern analysis.

This is NOT a machine-learned AI detector and makes no claim to reproduce
Turnitin's (proprietary, undisclosed) AI-writing model or its accuracy. It
surfaces a handful of publicly documented stylometric signals that
correlate -- loosely and imperfectly -- with unedited LLM output:

- low sentence-length variation ("burstiness" is a known human trait;
  LLM sampling tends to produce more uniform sentence lengths),
- a high density of stock transition/hedge phrases LLMs overuse
  ("moreover", "it is important to note", "delve into", ...),
- repeated sentence openers within a paragraph.

Every one of these signals also occurs naturally in careful, formal human
writing -- especially from non-native English writers, or writers who were
taught "signpost" transitions -- so this module is designed to flag
passages for a human to look at, never to accuse. See the "Limitations"
section rendered into every report, and README.md.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")

# Phrases widely reported (by researchers and by informal analysis of LLM
# output alike) as disproportionately common in unedited LLM writing.
# Deliberately NOT exhaustive or secret -- the point is transparency, not a
# hidden signature to game.
STOCK_PHRASES = [
    "moreover", "furthermore", "in conclusion", "it is important to note",
    "it is worth noting", "on the other hand", "overall,", "this highlights",
    "this underscores", "plays a crucial role", "plays a vital role",
    "in today's world", "delve into", "navigate the", "landscape of",
    "tapestry", "boasts", "the fact that", "in summary", "additionally,",
    "consequently,", "as a result,", "in essence", "notably,",
    "it is essential to", "serves as a", "underscoring", "multifaceted",
    "a testament to", "in the realm of", "it is crucial to",
]

WEIGHTS = {
    "low_sentence_variation": 0.45,
    "stock_phrase_density": 0.35,
    "opener_repetition": 0.20,
}


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


def split_paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in PARAGRAPH_SPLIT_RE.split(text) if p.strip()]
    if len(paras) <= 1:
        # No blank-line paragraph breaks (common after PDF extraction) --
        # fall back to grouping every few sentences into a pseudo-paragraph.
        sentences = split_sentences(text)
        paras = [" ".join(sentences[i : i + 4]) for i in range(0, len(sentences), 4)]
    return [p for p in paras if p.strip()]


@dataclass
class ParagraphScore:
    text: str
    score: float  # 0..1, higher = more consistent with unedited LLM output
    components: dict[str, float]
    confidence: str


@dataclass
class DocumentAnalysis:
    paragraphs: list[ParagraphScore]
    overall_score: float


def _low_sentence_variation_signal(sentences: list[str]) -> float:
    """0 = highly varied sentence lengths, 1 = suspiciously uniform."""
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) < 3:
        return 0.0
    mean = statistics.mean(lengths)
    if mean == 0:
        return 0.0
    coefficient_of_variation = statistics.pstdev(lengths) / mean
    # Typical human prose has cv well above ~0.4-0.5; below ~0.15 is unusual.
    return max(0.0, min(1.0, 1 - coefficient_of_variation / 0.8))


def _stock_phrase_density_signal(text: str) -> float:
    lower = text.lower()
    word_count = max(len(lower.split()), 1)
    hits = sum(lower.count(phrase) for phrase in STOCK_PHRASES)
    density_per_1000_words = hits / word_count * 1000
    return max(0.0, min(1.0, density_per_1000_words / 15))


def _opener_repetition_signal(sentences: list[str]) -> float:
    if len(sentences) < 3:
        return 0.0
    openers = [" ".join(s.split()[:2]).lower() for s in sentences]
    repeats = len(openers) - len(set(openers))
    return max(0.0, min(1.0, repeats / len(openers)))


def _confidence_label(score: float, n_sentences: int) -> str:
    if n_sentences < 3:
        return "insufficient text"
    if score < 0.35:
        return "low"
    if score < 0.55:
        return "moderate"
    if score < 0.75:
        return "elevated"
    return "high"


def score_paragraph(text: str) -> ParagraphScore:
    sentences = split_sentences(text)
    components = {
        "low_sentence_variation": _low_sentence_variation_signal(sentences),
        "stock_phrase_density": _stock_phrase_density_signal(text),
        "opener_repetition": _opener_repetition_signal(sentences),
    }
    score = sum(components[name] * weight for name, weight in WEIGHTS.items())
    confidence = _confidence_label(score, len(sentences))
    return ParagraphScore(text=text, score=score, components=components, confidence=confidence)


def analyze_document(text: str) -> DocumentAnalysis:
    paragraphs = [score_paragraph(p) for p in split_paragraphs(text)]
    if not paragraphs:
        return DocumentAnalysis(paragraphs=[], overall_score=0.0)
    weights = [max(len(p.text.split()), 1) for p in paragraphs]
    overall = sum(p.score * w for p, w in zip(paragraphs, weights)) / sum(weights)
    return DocumentAnalysis(paragraphs=paragraphs, overall_score=overall)
