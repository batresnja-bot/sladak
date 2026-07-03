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
<li>This score comes from a small set of <strong>publicly documented writing-style
statistics</strong> (sentence-length uniformity, stock transition phrases, repeated
sentence openers) &mdash; it is not a machine-learned classifier and does not see
what Turnitin's proprietary AI-writing model sees.</li>
<li>Every signal it uses also occurs naturally in careful, formal human writing.
Non-native English writers, writers taught to use "signpost" transitions, and
heavily copy-edited text are all more likely to score higher <em>without</em>
having used an AI tool.</li>
<li>A high score means "this passage's writing statistics resemble unedited LLM
output," not "this passage was written by AI." Treat it as a prompt to reread that
passage yourself, never as a verdict.</li>
<li>Short paragraphs (fewer than 3 sentences) are marked <code>insufficient text</code>
because these statistics are unreliable at that length.</li>
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


def _confidence_color(confidence: str) -> str:
    return {
        "insufficient text": "#eee",
        "low": "#e8f6ef",
        "moderate": "#fff3cd",
        "elevated": "#ffe0b3",
        "high": "#ffd1d1",
    }.get(confidence, "#eee")


def _render_ai_paragraphs(paragraphs: list[ParagraphScore]) -> str:
    blocks = []
    for p in paragraphs:
        color = _confidence_color(p.confidence)
        component_str = ", ".join(f"{k}: {v:.2f}" for k, v in p.components.items())
        blocks.append(
            f'<div class="paragraph" style="background:{color}">'
            f'<div class="paragraph-meta">score {p.score:.2f} &middot; '
            f'confidence: <strong>{html.escape(p.confidence)}</strong> '
            f'<span class="components">({html.escape(component_str)})</span></div>'
            f'<div class="paragraph-text">{html.escape(p.text)}</div>'
            f"</div>"
        )
    return "\n".join(blocks)


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
<div class="score"><span class="chip" style="background:#455a64">{ai_analysis.overall_score * 100:.0f}</span>
<small>/100 overall writing-pattern score
(higher = more consistent with unedited LLM output &mdash; see limitations below)</small></div>
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
