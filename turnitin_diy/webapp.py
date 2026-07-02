"""A minimal, no-login web front end for turnitin-diy.

Deployment model is "run this yourself," not "we run it for you": there is
no authentication, so if you put this on a public URL, anyone can submit a
document. To keep that safe:

- Uploaded files are processed inside a `tempfile.TemporaryDirectory()` that
  is deleted at the end of every request. Nothing is written to a database,
  logged, or kept around after the response is sent.
- `MAX_CONTENT_LENGTH` caps request size so one upload can't exhaust memory/disk.
- Requests are rate-limited per IP (via flask-limiter, if installed) since an
  anonymous public upload endpoint that does CPU work is a DoS target.
- The live-web spot-check (`websearch.py`, requires a paid Google API key) is
  intentionally not wired into this app -- an anonymous public endpoint is
  the wrong place to spend an API budget you don't control the usage of.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Flask, render_template, request

from .ai_detect import analyze_document
from .compare import build_source, find_matches
from .extract import SUPPORTED_SUFFIXES, extract_text
from .report import combined_report_html

MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB per request


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    analyze_view = _analyze
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(get_remote_address, app=app, default_limits=["20 per hour"])
        analyze_view = limiter.limit("5 per minute")(analyze_view)
    except ImportError:
        pass

    @app.get("/")
    def index():
        return render_template("upload.html", max_mb=MAX_CONTENT_LENGTH // (1024 * 1024))

    app.add_url_rule("/analyze", view_func=analyze_view, methods=["POST"])

    @app.errorhandler(413)
    def too_large(_exc):
        return "That file is larger than this server's upload limit.", 413

    return app


def _analyze():
    document = request.files.get("document")
    if document is None or not document.filename:
        return "No document uploaded.", 400

    suffix = Path(document.filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return f"Unsupported file type {suffix!r}. Use one of {sorted(SUPPORTED_SUFFIXES)}.", 400

    source_files = [f for f in request.files.getlist("sources") if f.filename]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        doc_path = tmp_path / Path(document.filename).name
        document.save(doc_path)
        try:
            target_text = extract_text(doc_path)
        except Exception as exc:  # noqa: BLE001 - surface extraction failures to the user
            return f"Could not read that file: {exc}", 400

        similarity_words = similarity_matches = None
        similarity_overlap = None
        if source_files:
            sources = []
            for i, f in enumerate(source_files):
                f_suffix = Path(f.filename).suffix.lower()
                if f_suffix not in SUPPORTED_SUFFIXES:
                    continue
                src_path = tmp_path / f"src_{i}_{Path(f.filename).name}"
                f.save(src_path)
                try:
                    sources.append(build_source(f.filename, extract_text(src_path)))
                except Exception:  # noqa: BLE001 - skip unreadable source files
                    continue
            if sources:
                similarity_words, similarity_matches, similarity_overlap = find_matches(target_text, sources)

        ai_analysis = analyze_document(target_text)

    return combined_report_html(
        title=document.filename,
        similarity_words=similarity_words,
        similarity_matches=similarity_matches,
        similarity_overlap=similarity_overlap,
        ai_analysis=ai_analysis,
        home_url="/",
    )


if __name__ == "__main__":
    create_app().run(debug=False)
