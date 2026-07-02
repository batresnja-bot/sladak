"""Render a Turnitin-style HTML similarity report: an overall score plus the
target text with matched passages highlighted and color-coded by source."""
from __future__ import annotations

import html
from pathlib import Path

from .compare import Match

PALETTE = ["#ffd166", "#06d6a0", "#ef476f", "#118ab2", "#8338ec", "#fb5607", "#3a86ff", "#c9184a"]


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
