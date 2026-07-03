"""Render Turnitin-style HTML reports.

Matches are highlighted in the *original* document text (punctuation,
capitalization, and line breaks intact) using the char offsets carried by
ComparisonResult -- the same way Turnitin renders a submission with colored
match blocks -- rather than re-joining lowercase tokens. Each source gets a
number and a color, listed Turnitin-style in a source list ordered by how
much of the document it accounts for, and the overall score is shown with
Turnitin's five color bands (blue / green / yellow / orange / red).
"""
from __future__ import annotations

import html
from pathlib import Path

from .ai_detect import DocumentAnalysis, ParagraphScore
from .compare import ComparisonResult, summarize_by_source
from .crosscheck import PairResult

PALETTE = ["#ffd166", "#06d6a0", "#ef476f", "#118ab2", "#8338ec", "#fb5607", "#3a86ff", "#c9184a"]

AI_LIMITATIONS_HTML = """
<div class="limitations">
<h2>Limitations &amp; false-positive warnings</h2>
<ul>
<li>These percentages come from a small set of <strong>publicly documented
writing-style statistics</strong> (sentence-length uniformity, stock phrases,
connector-opened sentences, em-dash density, repeated openers) &mdash; not a
machine-learned classifier. They will not match the percentage from Turnitin's
proprietary AI model, in either direction.</li>
<li>"AI-like" means "this paragraph's writing statistics resemble unedited LLM
output," not "this paragraph was written by AI." Every signal used here also
occurs naturally in careful, formal human writing. Non-native English writers,
writers taught to use "signpost" transitions, and heavily copy-edited text are
all more likely to land in the AI-like band <em>without</em> having used an AI
tool.</li>
<li>Treat the breakdown as a prompt to reread the flagged passages yourself,
never as a verdict.</li>
<li>Paragraphs with fewer than 3 sentences (headings, names, dates) are marked
<code>not scored</code> because these statistics are meaningless at that length;
they are excluded from the percentages.</li>
<li>Do not use this score, or any AI-detection score, as the sole basis for an
academic-integrity accusation.</li>
</ul>
</div>
"""


def similarity_band(overlap: float, has_matches: bool) -> tuple[str, str]:
    """Turnitin's five similarity-index bands: (band name, css color)."""
    pct = overlap * 100
    if not has_matches or pct == 0:
        return "blue", "#1e88e5"
    if pct < 25:
        return "green", "#43a047"
    if pct < 50:
        return "yellow", "#f9a825"
    if pct < 75:
        return "orange", "#fb8c00"
    return "red", "#e53935"


def _source_numbering(result: ComparisonResult) -> tuple[list[tuple[str, float]], dict[str, int], dict[str, str]]:
    """Turnitin numbers sources by contribution: source #1 is the biggest.
    Returns (breakdown, number_by_source, color_by_source)."""
    breakdown = summarize_by_source(len(result.words), result.matches)
    number_by_source = {sid: i + 1 for i, (sid, _) in enumerate(breakdown)}
    color_by_source = {sid: PALETTE[i % len(PALETTE)] for i, (sid, _) in enumerate(breakdown)}
    return breakdown, number_by_source, color_by_source


def _render_highlighted_text(
    result: ComparisonResult,
    number_by_source: dict[str, int],
    color_by_source: dict[str, str],
) -> str:
    """The document view: original text with match blocks wrapped in <mark>,
    each carrying its source number badge, Turnitin-style."""
    text, spans, words = result.text, result.word_spans, result.words
    parts: list[str] = []
    cursor = 0
    for m in result.matches:
        last_word = min(m.target_end, len(words)) - 1
        if last_word < m.target_start:
            continue
        char_start = spans[m.target_start][0]
        char_end = spans[last_word][1]
        if char_start > cursor:
            parts.append(html.escape(text[cursor:char_start]))
        if char_end > cursor:
            color = color_by_source[m.source_id]
            num = number_by_source[m.source_id]
            chunk = html.escape(text[max(cursor, char_start):char_end])
            parts.append(
                f'<mark style="background:{color}" title="{html.escape(m.source_id)}">'
                f'<sup class="srcnum">{num}</sup>{chunk}</mark>'
            )
        cursor = max(cursor, char_end)
    if cursor < len(text):
        parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def _score_chip(overlap: float, has_matches: bool) -> str:
    band, color = similarity_band(overlap, has_matches)
    return (
        f'<span class="chip" style="background:{color}">{overlap * 100:.0f}%</span>'
        f'<span class="band-label">similarity band: {band}</span>'
    )


def _similarity_section_html(result: ComparisonResult, filters_note: str | None) -> str:
    breakdown, number_by_source, color_by_source = _source_numbering(result)
    legend_items = "".join(
        f'<li><span class="swatch" style="background:{color_by_source[sid]}"></span>'
        f"<strong>{number_by_source[sid]}</strong>&nbsp;{html.escape(sid)} &mdash; {frac * 100:.1f}%</li>"
        for sid, frac in breakdown
    )
    filters_line = (
        f'<p class="filters">Score filters: {html.escape(filters_note)}</p>' if filters_note else ""
    )
    return f"""
<h2>Similarity (text-overlap) match</h2>
<div class="score">{_score_chip(result.overlap, bool(result.matches))}
<small>{result.overlap * 100:.1f}% of words fall inside a matched passage,
across {len(result.matches)} passage(s) and {len(breakdown)} source(s)</small></div>
{filters_line}
<ul class="legend">{legend_items}</ul>
<div class="text">{_render_highlighted_text(result, number_by_source, color_by_source)}</div>
"""


REPORT_CSS = """
body { font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 2rem auto;
       padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }
h2 { margin-top: 2.5rem; border-bottom: 2px solid #eee; padding-bottom: 0.4rem; }
.score { font-size: 1.1rem; margin: 1rem 0; }
.score small { display: block; font-size: 0.9rem; color: #555; margin-top: 0.4rem; }
.chip { display: inline-block; color: white; font-size: 1.8rem; font-weight: 700;
        padding: 0.15rem 0.8rem; border-radius: 8px; }
.band-label { margin-left: 0.75rem; color: #555; font-size: 0.9rem; }
.swatch { display: inline-block; width: 12px; height: 12px; margin-right: 6px; border-radius: 2px; vertical-align: middle; }
ul.legend { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 12px; margin: 1rem 0; }
mark { border-radius: 2px; padding: 0 2px; }
mark .srcnum { font-size: 0.65rem; font-weight: 700; margin-right: 2px; }
.text { white-space: pre-wrap; border: 1px solid #ddd; padding: 1.5rem; border-radius: 8px; margin-top: 1.5rem; }
.paragraphs { margin-top: 1rem; }
.paragraph { border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }
.paragraph-meta { font-size: 0.8rem; color: #444; margin-bottom: 0.4rem; }
.paragraph-meta .components { color: #777; }
.limitations { background: #f7f7f7; border-radius: 8px; padding: 1.25rem 1.5rem; margin-top: 2.5rem; }
.limitations h2 { margin-top: 0; border: none; }
.filters { font-size: 0.85rem; color: #666; }
.ai-stats { display: flex; flex-wrap: wrap; gap: 1.5rem; font-size: 1.5rem; font-weight: 700; margin: 1rem 0 0.5rem; }
.stackbar { display: flex; height: 18px; border-radius: 9px; overflow: hidden; background: #eee; margin: 0.5rem 0; }
.stackbar span { display: block; height: 100%; }
.ai-note { font-size: 0.85rem; color: #666; margin: 0.4rem 0; }
"""


def render_report(title: str, result: ComparisonResult, out_path: Path) -> None:
    """Similarity-only report."""
    doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Similarity report: {html.escape(title)}</title>
<style>{REPORT_CSS}</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
{_similarity_section_html(result, filters_note=None)}
</body>
</html>
"""
    out_path.write_text(doc, encoding="utf-8")


AI_CLASS_COLORS = {
    "ai-like": ("#e53935", "#ffd1d1"),
    "mixed": ("#f9a825", "#fff3cd"),
    "human-like": ("#43a047", "#e8f6ef"),
    "not scored": ("#9e9e9e", "#eee"),
}

AI_CLASS_LABELS = {
    "ai-like": "AI-like",
    "mixed": "Mixed / unclear",
    "human-like": "Human-like",
    "not scored": "Not scored (too short)",
}


def _render_ai_paragraphs(paragraphs: list[ParagraphScore]) -> str:
    blocks = []
    for p in paragraphs:
        strong, background = AI_CLASS_COLORS.get(p.classification, ("#9e9e9e", "#eee"))
        label = AI_CLASS_LABELS.get(p.classification, p.classification)
        component_str = ", ".join(f"{k}: {v:.2f}" for k, v in p.components.items())
        blocks.append(
            f'<div class="paragraph" style="background:{background}">'
            f'<div class="paragraph-meta"><strong style="color:{strong}">{html.escape(label)}</strong>'
            f" &middot; score {p.score:.2f} "
            f'<span class="components">({html.escape(component_str)})</span></div>'
            f'<div class="paragraph-text">{html.escape(p.text)}</div>'
            f"</div>"
        )
    return "\n".join(blocks)


def _ai_breakdown_html(ai: DocumentAnalysis) -> str:
    """The Turnitin-style headline: AI-like X% / Mixed Y% / Human-like Z% of
    the document's scoreable words, plus a stacked bar."""
    if ai.scored_words == 0:
        return (
            '<p class="ai-note">Not enough text to analyze &mdash; no paragraph has 3 or more '
            "sentences, which these statistics need to mean anything.</p>"
        )
    ai_pct = round(ai.ai_fraction * 100)
    mixed_pct = round(ai.mixed_fraction * 100)
    human_pct = 100 - ai_pct - mixed_pct
    segments = "".join(
        f'<span style="width:{pct}%;background:{color}"></span>'
        for pct, color in (
            (ai_pct, AI_CLASS_COLORS["ai-like"][0]),
            (mixed_pct, AI_CLASS_COLORS["mixed"][0]),
            (human_pct, AI_CLASS_COLORS["human-like"][0]),
        )
        if pct > 0
    )
    unscored_note = ""
    if ai.unscored_words:
        unscored_note = (
            f'<p class="ai-note">{ai.unscored_words} word(s) in headings and short blocks were '
            "too short to score and are not counted in the percentages.</p>"
        )
    return f"""
<div class="ai-stats">
<span class="stat" style="color:{AI_CLASS_COLORS['ai-like'][0]}">AI-like: {ai_pct}%</span>
<span class="stat" style="color:{AI_CLASS_COLORS['mixed'][0]}">Mixed: {mixed_pct}%</span>
<span class="stat" style="color:{AI_CLASS_COLORS['human-like'][0]}">Human-like: {human_pct}%</span>
</div>
<div class="stackbar">{segments}</div>
<p class="ai-note">Share of the document's words whose paragraph writing statistics fall in each
class &mdash; a prompt to reread those passages, not a verdict (see limitations below).</p>
{unscored_note}"""


def combined_report_html(
    title: str,
    similarity: ComparisonResult | None,
    ai_analysis: DocumentAnalysis,
    home_url: str | None = None,
    filters_note: str | None = None,
) -> str:
    similarity_section = _similarity_section_html(similarity, filters_note) if similarity else ""

    ai_section = f"""
<h2>Writing-pattern (AI-likelihood) analysis</h2>
{_ai_breakdown_html(ai_analysis)}
<div class="paragraphs">{_render_ai_paragraphs(ai_analysis.paragraphs)}</div>
"""

    back_link = f'<p><a href="{html.escape(home_url)}">&larr; check another document</a></p>' if home_url else ""

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Report: {html.escape(title)}</title>
<style>{REPORT_CSS}</style>
</head>
<body>
{back_link}
<h1>{html.escape(title)}</h1>
{similarity_section}
{ai_section}
{AI_LIMITATIONS_HTML}
</body>
</html>
"""


def render_combined_report(
    title: str,
    similarity: ComparisonResult | None,
    ai_analysis: DocumentAnalysis,
    out_path: Path,
    filters_note: str | None = None,
) -> None:
    doc = combined_report_html(
        title=title, similarity=similarity, ai_analysis=ai_analysis, filters_note=filters_note
    )
    out_path.write_text(doc, encoding="utf-8")


def _overlap_color(fraction: float) -> str:
    if fraction >= 0.5:
        return "#ffd1d1"
    if fraction >= 0.25:
        return "#ffe0b3"
    if fraction >= 0.10:
        return "#fff3cd"
    return "#e8f6ef"


def crosscheck_report_html(title: str, results: list[PairResult]) -> str:
    rows = "".join(
        f"<tr style=\"background:{_overlap_color(r.max_overlap)}\">"
        f"<td>{html.escape(r.doc_a)}</td><td>{html.escape(r.doc_b)}</td>"
        f"<td>{r.overlap_a_in_b * 100:.1f}%</td><td>{r.overlap_b_in_a * 100:.1f}%</td></tr>"
        for r in results
    )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Cross-check: {html.escape(title)}</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 860px; margin: 2rem auto;
        padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1.5rem; }}
th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #ddd; }}
th {{ font-size: 0.85rem; color: #555; }}
p.hint {{ color: #666; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>Cross-check: {html.escape(title)}</h1>
<p class="hint">Every document compared against every other, both directions
(collusion-style check). Pairs sorted by highest overlap. Run
<code>sladak check A --sources folder-with-B</code> on a suspicious pair
to see the exact matched passages.</p>
<table>
<tr><th>Document A</th><th>Document B</th><th>A matched in B</th><th>B matched in A</th></tr>
{rows}
</table>
</body>
</html>
"""


def render_crosscheck_report(title: str, results: list[PairResult], out_path: Path) -> None:
    out_path.write_text(crosscheck_report_html(title, results), encoding="utf-8")
