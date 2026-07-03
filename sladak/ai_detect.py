"""Heuristic, fully transparent writing-pattern analysis.

This is NOT a machine-learned AI detector and makes no claim to reproduce
Turnitin's (proprietary, undisclosed) AI-writing model or its accuracy. It
surfaces publicly documented stylometric signals that correlate -- loosely
and imperfectly -- with unedited LLM output:

- low sentence-length variation ("burstiness" is a known human trait;
  LLM sampling tends to produce more uniform sentence lengths),
- a high density of stock words/phrases LLMs statistically overuse
  ("moreover", "it is important to note", "delve into", "multifaceted", ...),
- a high fraction of sentences opened with a transition connector
  ("However,", "Furthermore,", "Additionally,", ...),
- nominalization-dense formality ("disruption", "fragmentation",
  "implications", ...) and consistently long sentences,
- em-dash-heavy punctuation style,
- repeated sentence openers within a paragraph.

Each paragraph's weighted signal sum is passed through a logistic curve and
classified Turnitin-report-style as AI-like / mixed / human-like, and the
document header reports what share of the document's words falls in each
class. Headings and very short blocks are excluded ("not scored") rather
than counted as human.

Every one of these signals also occurs naturally in careful, formal human
writing -- especially from non-native English writers, or writers who were
taught "signpost" transitions -- so this module is designed to flag
passages for a human to look at, never to accuse. See the "Limitations"
section rendered into every report, and README.md.
"""
from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")

# Words/phrases widely reported (in stylometry research and large-scale corpus
# comparisons of pre/post-LLM text alike) as disproportionately common in
# unedited LLM output. Deliberately NOT exhaustive or secret -- the point is
# transparency, not a hidden signature to game.
STOCK_PHRASES = [
    # discourse markers
    "moreover", "furthermore", "in conclusion", "in summary", "in essence",
    "additionally,", "consequently,", "as a result,", "notably,", "overall,",
    "importantly,", "crucially,", "in turn,", "taken together",
    # hedges / signposts
    "it is important to note", "it is worth noting", "it is essential to",
    "it is crucial to", "this highlights", "this underscores", "underscoring",
    "highlights the importance", "highlights the need", "underscores the need",
    "the fact that", "on the other hand",
    # LLM-flavored vocabulary
    "delve into", "delves into", "navigate the", "navigating the",
    "landscape of", "tapestry", "multifaceted", "a testament to",
    "in the realm of", "plays a crucial role", "plays a vital role",
    "plays a pivotal role", "pivotal role", "serves as a", "stands as a",
    "remains a cornerstone", "paving the way", "poised to",
    "transformative", "unprecedented", "holistic", "nuanced understanding",
    "comprehensive framework", "comprehensive overview", "comprehensive analysis",
    "significant implications", "far-reaching implications",
    "rapidly evolving", "ever-evolving", "in today's world",
    "garnered significant", "marked a significant", "boasts",
    # analysis-paper connectors
    "with respect to", "in the context of", "through the lens of",
    "a wide range of", "a variety of factors", "key drivers",
    "shed light on", "sheds light on", "shedding light on",
]

# Sentence-initial transition connectors. Unedited LLM prose opens an
# unusually high fraction of sentences with one of these.
CONNECTOR_OPENERS = [
    "however", "moreover", "furthermore", "additionally", "consequently",
    "therefore", "thus", "hence", "similarly", "conversely", "meanwhile",
    "ultimately", "finally", "notably", "importantly", "crucially",
    "specifically", "subsequently", "accordingly", "nevertheless",
    "nonetheless", "in addition", "in contrast", "in turn", "as a result",
    "as such", "in sum", "in summary", "in conclusion", "on the other hand",
    "at the same time", "taken together", "first", "second", "third",
    "overall", "in particular", "more broadly", "against this backdrop",
]

EM_DASH_RE = re.compile(r"—|\s–\s")  # em dash, or spaced en dash used as one

# Abstract-noun suffixes: LLM formal prose is unusually nominalization-dense
# ("disruption", "fragmentation", "implications", "transmission", ...).
NOMINALIZATION_RE = re.compile(
    r"\b\w{4,}(?:tions?|sions?|ments?|ances?|ences?|ities|ity|ness|izations?|isations?)\b",
    re.IGNORECASE,
)

WEIGHTS = {
    "low_sentence_variation": 0.20,
    "stock_phrase_density": 0.25,
    "connector_openers": 0.20,
    "nominalization_density": 0.15,
    "long_sentences": 0.10,
    "em_dash_style": 0.05,
    "opener_repetition": 0.05,
}

# Logistic calibration: raw weighted sums cluster in 0.1-0.7, so squash them
# onto the full 0-1 range. Midpoint 0.30 = the gray zone where careful formal
# human writing and LLM output genuinely overlap.
CALIBRATION_MIDPOINT = 0.30
CALIBRATION_STEEPNESS = 8.0

AI_THRESHOLD = 0.65
HUMAN_THRESHOLD = 0.40

NOT_SCORED = "not scored"


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
    score: float  # 0..1 calibrated, higher = more consistent with unedited LLM output
    components: dict[str, float]
    classification: str  # "ai-like" | "mixed" | "human-like" | "not scored"


@dataclass
class DocumentAnalysis:
    paragraphs: list[ParagraphScore]
    overall_score: float
    # Word-weighted shares of the *scored* portion of the document.
    ai_fraction: float
    mixed_fraction: float
    human_fraction: float
    scored_words: int
    unscored_words: int


def _low_sentence_variation_signal(sentences: list[str]) -> float:
    """0 = bursty human-like sentence lengths, 1 = suspiciously uniform.
    Human prose usually has a coefficient of variation above ~0.5; unedited
    LLM output often sits below ~0.35."""
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) < 3:
        return 0.0
    mean = statistics.mean(lengths)
    if mean == 0:
        return 0.0
    cv = statistics.pstdev(lengths) / mean
    return max(0.0, min(1.0, (0.55 - cv) / 0.40))


def _stock_phrase_density_signal(text: str) -> float:
    lower = text.lower()
    word_count = max(len(lower.split()), 1)
    hits = sum(lower.count(phrase) for phrase in STOCK_PHRASES)
    density_per_1000_words = hits / word_count * 1000
    return max(0.0, min(1.0, density_per_1000_words / 20))


def _connector_openers_signal(sentences: list[str]) -> float:
    """Fraction of sentences that open with a transition connector; ~10% is
    unremarkable, ~45%+ is the LLM signpost-every-sentence pattern."""
    if len(sentences) < 3:
        return 0.0
    hits = 0
    for s in sentences:
        head = s.lower().lstrip("\"'“‘(")
        if any(head.startswith(c + " ") or head.startswith(c + ",") for c in CONNECTOR_OPENERS):
            hits += 1
    fraction = hits / len(sentences)
    return max(0.0, min(1.0, (fraction - 0.10) / 0.35))


def _nominalization_density_signal(text: str) -> float:
    """Abstract-noun (nominalization) density per 1000 words. Conversational
    prose sits near 0-30; LLM formal prose commonly reaches 90-150. Careful
    human academic writing lands in between -- which is why this signal only
    pushes toward the "mixed" band on its own."""
    word_count = max(len(text.split()), 1)
    density_per_1000_words = len(NOMINALIZATION_RE.findall(text)) / word_count * 1000
    return max(0.0, min(1.0, (density_per_1000_words - 30) / 60))


def _long_sentences_signal(sentences: list[str]) -> float:
    """Mean sentence length in words; LLM formal prose runs long (25-45)."""
    if len(sentences) < 3:
        return 0.0
    mean_len = statistics.mean(len(s.split()) for s in sentences)
    return max(0.0, min(1.0, (mean_len - 15) / 15))


def _em_dash_style_signal(text: str) -> float:
    """Em-dash-per-1000-words density; heavy em-dash use is one of the most
    widely reported tells of unedited LLM prose."""
    word_count = max(len(text.split()), 1)
    density_per_1000_words = len(EM_DASH_RE.findall(text)) / word_count * 1000
    return max(0.0, min(1.0, density_per_1000_words / 6))


def _opener_repetition_signal(sentences: list[str]) -> float:
    if len(sentences) < 3:
        return 0.0
    openers = [" ".join(s.split()[:2]).lower() for s in sentences]
    repeats = len(openers) - len(set(openers))
    return max(0.0, min(1.0, repeats / len(openers)))


def _calibrate(raw: float) -> float:
    return 1.0 / (1.0 + math.exp(-(raw - CALIBRATION_MIDPOINT) * CALIBRATION_STEEPNESS))


def _classify(score: float, n_sentences: int) -> str:
    if n_sentences < 3:
        return NOT_SCORED
    if score >= AI_THRESHOLD:
        return "ai-like"
    if score >= HUMAN_THRESHOLD:
        return "mixed"
    return "human-like"


def score_paragraph(text: str) -> ParagraphScore:
    sentences = split_sentences(text)
    components = {
        "low_sentence_variation": _low_sentence_variation_signal(sentences),
        "stock_phrase_density": _stock_phrase_density_signal(text),
        "connector_openers": _connector_openers_signal(sentences),
        "nominalization_density": _nominalization_density_signal(text),
        "long_sentences": _long_sentences_signal(sentences),
        "em_dash_style": _em_dash_style_signal(text),
        "opener_repetition": _opener_repetition_signal(sentences),
    }
    raw = sum(components[name] * weight for name, weight in WEIGHTS.items())
    score = _calibrate(raw) if len(sentences) >= 3 else 0.0
    classification = _classify(score, len(sentences))
    return ParagraphScore(text=text, score=score, components=components, classification=classification)


def analyze_document(text: str) -> DocumentAnalysis:
    paragraphs = [score_paragraph(p) for p in split_paragraphs(text)]
    if not paragraphs:
        return DocumentAnalysis(
            paragraphs=[], overall_score=0.0,
            ai_fraction=0.0, mixed_fraction=0.0, human_fraction=0.0,
            scored_words=0, unscored_words=0,
        )

    class_words = {"ai-like": 0, "mixed": 0, "human-like": 0, NOT_SCORED: 0}
    weighted_score_sum = 0.0
    for p in paragraphs:
        n_words = max(len(p.text.split()), 1)
        class_words[p.classification] += n_words
        if p.classification != NOT_SCORED:
            weighted_score_sum += p.score * n_words

    scored_words = class_words["ai-like"] + class_words["mixed"] + class_words["human-like"]
    unscored_words = class_words[NOT_SCORED]
    if scored_words == 0:
        return DocumentAnalysis(
            paragraphs=paragraphs, overall_score=0.0,
            ai_fraction=0.0, mixed_fraction=0.0, human_fraction=0.0,
            scored_words=0, unscored_words=unscored_words,
        )

    return DocumentAnalysis(
        paragraphs=paragraphs,
        overall_score=weighted_score_sum / scored_words,
        ai_fraction=class_words["ai-like"] / scored_words,
        mixed_fraction=class_words["mixed"] / scored_words,
        human_fraction=class_words["human-like"] / scored_words,
        scored_words=scored_words,
        unscored_words=unscored_words,
    )
