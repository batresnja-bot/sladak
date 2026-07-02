from __future__ import annotations

import argparse
from pathlib import Path

from .compare import build_source, find_matches
from .extract import SUPPORTED_SUFFIXES, extract_text
from .report import render_report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="turnitin-diy", description="A local text-similarity checker.")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Compare a document against a folder of reference sources.")
    check.add_argument("document", type=Path, help="Your paper (.docx, .pdf, .txt, or .md)")
    check.add_argument("--sources", type=Path, required=True, help="Folder of reference files to compare against")
    check.add_argument("--out", type=Path, default=Path("report.html"), help="Where to write the HTML report")
    check.add_argument("--k", type=int, default=8, help="Shingle length in words (default: 8)")
    check.add_argument("--window", type=int, default=4, help="Winnowing window size (default: 4)")
    check.add_argument("--min-run", type=int, default=8, help="Minimum matched run in words to report (default: 8)")
    check.add_argument("--web", action="store_true", help="Also spot-check long sentences against the live web")

    args = parser.parse_args(argv)
    if args.command == "check":
        run_check(args)


def run_check(args: argparse.Namespace) -> None:
    target_text = extract_text(args.document)

    source_files = [p for p in args.sources.rglob("*") if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not source_files:
        raise SystemExit(f"No reference files found in {args.sources} (looked for {sorted(SUPPORTED_SUFFIXES)})")

    sources = []
    for path in source_files:
        try:
            text = extract_text(path)
        except Exception as exc:  # noqa: BLE001 - keep checking remaining sources
            print(f"  skipping {path.name}: {exc}")
            continue
        sources.append(build_source(path.name, text, k=args.k, window=args.window))

    words, matches, overlap = find_matches(
        target_text, sources, k=args.k, window=args.window, min_run=args.min_run
    )

    render_report(title=args.document.name, words=words, matches=matches, overlap=overlap, out_path=args.out)

    print(f"{overlap * 100:.1f}% word overlap across {len(matches)} matched passage(s) and {len(sources)} source(s).")
    print(f"Report written to {args.out.resolve()}")

    if args.web:
        from .websearch import check_web

        try:
            hits = check_web(target_text)
        except RuntimeError as exc:
            print(f"\nWeb check skipped: {exc}")
        else:
            print(f"\nWeb check: {len(hits)} hit(s) for exact-phrase queries built from your longest sentences.")
            for hit in hits:
                print(f"  - {hit.title} ({hit.url})")


if __name__ == "__main__":
    main()
