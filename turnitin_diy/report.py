"""Render Turnitin-style HTML reports: a similarity report (matched passages
highlighted and color-coded by source) and a combined report that also
includes the AI-writing-pattern analysis, paragraph by paragraph, with
explicit confidence labels and a limitations/false-positive section."""
from __future__ import annotations

import html
from pathlib import Path

from .ai_detect import DocumentAnalysis, ParagraphScore
from .compare import Match

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


def render_report(
    title: str,
    words: list[str],
    matches: list[Match],
    overlap: float,
    out_path: Path,
) -> None:
    source_ids = sorted({m.source_id for m in matches})
    color_by_source = {sid: PALETTE[i % len(PALETTE)] for i, sid in enumerate(source_ids)}

    body_parts: list[str] = []
    cursor = 0
    for m in matches:
        if m.target_start > cursor:
            body_parts.append(html.escape(" ".join(words[cursor : m.target_start])))
        color = color_by_source[m.source_id]
        chunk = html.escape(" ".join(words[m.target_start : m.target_end]))
        body_parts.append(f'<mark style="background:{color}" title="{html.escape(m.source_id)}">{chunk}</mark>')
        cursor = max(cursor, m.target_end)
    if cursor < len(words):
        body_parts.append(html.escape(" ".join(words[cursor:])))

    legend_items = "".join(
        f'<li><span class="swatch" style="background:{color}"></span>{html.escape(sid)}</li>'
        for sid, color in color_by_source.items()
    )

    doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Similarity report: {html.escape(title)}</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 860px; margin: 2rem auto;
        padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
.score {{ font-size: 2.25rem; font-weight: 700; }}
.score small {{ display:block; font-size: 0.9rem; font-weight: 400; color: #555; }}
.swatch {{ display:inline-block; width:12px; height:12px; margin-right:6px; border-radius:2px; vertical-align: middle; }}
ul.legend {{ list-style:none; padding:0; display:flex; flex-wrap:wrap; gap:12px; margin: 1rem 0; }}
mark {{ border-radius:2px; padding:0 2px; }}
.text {{ white-space: pre-wrap; border: 1px solid #ddd; padding: 1.5rem; border-radius: 8px; margin-top: 1.5rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="score">{overlap * 100:.1f}%<small>of words fall inside a matched passage, across {len(matches)} passage(s) and {len(source_ids)} source(s)</small></div>
<ul class="legend">{legend_items}</ul>
<div class="text">{' '.join(body_parts)}</div>
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


def render_combined_report(
    title: str,
    similarity_words: list[str] | None,
    similarity_matches: list[Match] | None,
    similarity_overlap: float | None,
    ai_analysis: DocumentAnalysis,
    out_path: Path,
) -> None:
    has_similarity = similarity_words is not None and similarity_matches is not None

    similarity_section = ""
    if has_similarity:
        source_ids = sorted({m.source_id for m in similarity_matches})
        color_by_source = {sid: PALETTE[i % len(PALETTE)] for i, sid in enumerate(source_ids)}
        body_parts: list[str] = []
        cursor = 0
        for m in similarity_matches:
            if m.target_start > cursor:
                body_parts.append(html.escape(" ".join(similarity_words[cursor : m.target_start])))
            color = color_by_source[m.source_id]
            chunk = html.escape(" ".join(similarity_words[m.target_start : m.target_end]))
            body_parts.append(f'<mark style="background:{color}" title="{html.escape(m.source_id)}">{chunk}</mark>')
            cursor = max(cursor, m.target_end)
        if cursor < len(similarity_words):
            body_parts.append(html.escape(" ".join(similarity_words[cursor:])))
        legend_items = "".join(
            f'<li><span class="swatch" style="background:{color}"></span>{html.escape(sid)}</li>'
            for sid, color in color_by_source.items()
        )
        similarity_section = f"""
<h2>Similarity (text-overlap) match</h2>
<div class="score">{similarity_overlap * 100:.1f}%<small>of words fall inside a matched passage,
across {len(similarity_matches)} passage(s) and {len(source_ids)} source(s)</small></div>
<ul class="legend">{legend_items}</ul>
<div class="text">{' '.join(body_parts)}</div>
"""

    ai_section = f"""
<h2>Writing-pattern (AI-likelihood) analysis</h2>
<div class="score">{ai_analysis.overall_score * 100:.0f}<small>/100 overall writing-pattern score
(higher = more consistent with unedited LLM output &mdash; see limitations below)</small></div>
<div class="paragraphs">{_render_ai_paragraphs(ai_analysis.paragraphs)}</div>
"""

    doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Report: {html.escape(title)}</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 2rem auto;
        padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
h2 {{ margin-top: 2.5rem; border-bottom: 2px solid #eee; padding-bottom: 0.4rem; }}
.score {{ font-size: 2.25rem; font-weight: 700; }}
.score small {{ display:block; font-size: 0.9rem; font-weight: 400; color: #555; }}
.swatch {{ display:inline-block; width:12px; height:12px; margin-right:6px; border-radius:2px; vertical-align: middle; }}
ul.legend {{ list-style:none; padding:0; display:flex; flex-wrap:wrap; gap:12px; margin: 1rem 0; }}
mark {{ border-radius:2px; padding:0 2px; }}
.text {{ white-space: pre-wrap; border: 1px solid #ddd; padding: 1.5rem; border-radius: 8px; margin-top: 1.5rem; }}
.paragraphs {{ margin-top: 1rem; }}
.paragraph {{ border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; }}
.paragraph-meta {{ font-size: 0.8rem; color: #444; margin-bottom: 0.4rem; }}
.paragraph-meta .components {{ color: #777; }}
.limitations {{ background: #f7f7f7; border-radius: 8px; padding: 1.25rem 1.5rem; margin-top: 2.5rem; }}
.limitations h2 {{ margin-top: 0; border: none; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
{similarity_section}
{ai_section}
{AI_LIMITATIONS_HTML}
</body>
</html>
"""
    out_path.write_text(doc, encoding="utf-8")
