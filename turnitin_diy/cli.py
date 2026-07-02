from __future__ import annotations

import argparse
from pathlib import Path

from .ai_detect import analyze_document
from .compare import Source, build_source, find_matches
from .corpus import DEFAULT_DB, Corpus
from .extract import SUPPORTED_SUFFIXES, extract_text
from .filters import describe_filters
from .report import render_combined_report, render_crosscheck_report, render_report


def _add_matching_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--k", type=int, default=8, help="Shingle length in words (default: 8)")
    p.add_argument("--window", type=int, default=4, help="Winnowing window size (default: 4)")
    p.add_argument("--min-run", type=int, default=8, help="Minimum matched run in words to report (default: 8)")


def _add_filter_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--exclude-quotes", action="store_true", help="Don't count quoted material toward the score")
    p.add_argument(
        "--exclude-bibliography", action="store_true", help="Don't count the references section toward the score"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="turnitin-diy", description="A local text-similarity checker.")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Compare a document against reference sources and/or your corpus.")
    check.add_argument("document", type=Path, help="Your paper (.docx, .pdf, .txt, or .md)")
    check.add_argument("--sources", type=Path, default=None, help="Folder of reference files to compare against")
    check.add_argument("--corpus", type=Path, default=None, help="Corpus database to also compare against")
    check.add_argument("--out", type=Path, default=Path("report.html"), help="Where to write the HTML report")
    _add_matching_args(check)
    _add_filter_args(check)
    check.add_argument("--web", action="store_true", help="Also spot-check long sentences against the live web")

    report = sub.add_parser(
        "report", help="Full report: similarity match (optional) + AI-writing-pattern analysis."
    )
    report.add_argument("document", type=Path, help="Your paper (.docx, .pdf, .txt, or .md)")
    report.add_argument(
        "--sources", type=Path, default=None, help="Optional folder of reference files for the similarity check"
    )
    report.add_argument("--corpus", type=Path, default=None, help="Corpus database to also compare against")
    report.add_argument("--out", type=Path, default=Path("report.html"), help="Where to write the HTML report")
    _add_matching_args(report)
    _add_filter_args(report)

    crosscheck = sub.add_parser(
        "crosscheck", help="Compare every document in a folder against every other (collusion check)."
    )
    crosscheck.add_argument("folder", type=Path, help="Folder of documents to cross-compare")
    crosscheck.add_argument("--out", type=Path, default=Path("crosscheck.html"), help="Where to write the HTML report")
    _add_matching_args(crosscheck)

    corpus = sub.add_parser("corpus", help="Manage your persistent reference corpus (your own Turnitin archive).")
    corpus_sub = corpus.add_subparsers(dest="corpus_command", required=True)
    corpus_add = corpus_sub.add_parser("add", help="Add documents to the corpus.")
    corpus_add.add_argument("files", type=Path, nargs="+", help="Files to add")
    corpus_add.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"Corpus database (default: {DEFAULT_DB})")
    corpus_list = corpus_sub.add_parser("list", help="List documents in the corpus.")
    corpus_list.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"Corpus database (default: {DEFAULT_DB})")
    corpus_remove = corpus_sub.add_parser("remove", help="Remove a document from the corpus by id.")
    corpus_remove.add_argument("doc_id", type=int, help="Document id (see `corpus list`)")
    corpus_remove.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"Corpus database (default: {DEFAULT_DB})")

    args = parser.parse_args(argv)
    if args.command == "check":
        run_check(args)
    elif args.command == "report":
        run_report(args)
    elif args.command == "crosscheck":
        run_crosscheck(args)
    elif args.command == "corpus":
        run_corpus(args)


def _collect_sources(args: argparse.Namespace) -> list[Source]:
    sources: list[Source] = []
    if args.sources is not None:
        source_files = [p for p in args.sources.rglob("*") if p.suffix.lower() in SUPPORTED_SUFFIXES]
        for path in source_files:
            try:
                text = extract_text(path)
            except Exception as exc:  # noqa: BLE001 - keep checking remaining sources
                print(f"  skipping {path.name}: {exc}")
                continue
            sources.append(build_source(path.name, text, k=args.k, window=args.window))
    if args.corpus is not None:
        if not args.corpus.exists():
            raise SystemExit(f"Corpus database not found: {args.corpus}")
        with Corpus(args.corpus) as corpus:
            sources.extend(corpus.build_sources(k=args.k, window=args.window))
    return sources


def run_check(args: argparse.Namespace) -> None:
    if args.sources is None and args.corpus is None:
        raise SystemExit("Provide --sources and/or --corpus to compare against.")
    target_text = extract_text(args.document)
    sources = _collect_sources(args)
    if not sources:
        raise SystemExit("No readable reference documents found.")

    words, matches, overlap = find_matches(
        target_text,
        sources,
        k=args.k,
        window=args.window,
        min_run=args.min_run,
        exclude_quotes=args.exclude_quotes,
        exclude_bibliography=args.exclude_bibliography,
    )

    render_report(title=args.document.name, words=words, matches=matches, overlap=overlap, out_path=args.out)

    filters_note = describe_filters(args.exclude_quotes, args.exclude_bibliography)
    if filters_note:
        print(f"Score filters: {filters_note}")
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


def run_report(args: argparse.Namespace) -> None:
    target_text = extract_text(args.document)

    similarity_words = similarity_matches = None
    similarity_overlap = None
    if args.sources is not None or args.corpus is not None:
        sources = _collect_sources(args)
        if not sources:
            raise SystemExit("No readable reference documents found.")
        similarity_words, similarity_matches, similarity_overlap = find_matches(
            target_text,
            sources,
            k=args.k,
            window=args.window,
            min_run=args.min_run,
            exclude_quotes=args.exclude_quotes,
            exclude_bibliography=args.exclude_bibliography,
        )

    ai_analysis = analyze_document(target_text)

    render_combined_report(
        title=args.document.name,
        similarity_words=similarity_words,
        similarity_matches=similarity_matches,
        similarity_overlap=similarity_overlap,
        ai_analysis=ai_analysis,
        out_path=args.out,
        filters_note=describe_filters(args.exclude_quotes, args.exclude_bibliography),
    )

    if similarity_overlap is not None:
        print(f"Similarity: {similarity_overlap * 100:.1f}% word overlap across {len(similarity_matches)} passage(s).")
    print(f"Writing-pattern score: {ai_analysis.overall_score * 100:.0f}/100 (see report for per-paragraph detail).")
    print(f"Report written to {args.out.resolve()}")


def run_crosscheck(args: argparse.Namespace) -> None:
    from .crosscheck import crosscheck_folder

    results = crosscheck_folder(args.folder, k=args.k, window=args.window, min_run=args.min_run)
    if not results:
        raise SystemExit(f"Need at least two readable documents in {args.folder} to cross-check.")

    render_crosscheck_report(title=args.folder.name, results=results, out_path=args.out)

    print(f"Cross-checked {len(results)} pair(s). Highest overlaps:")
    for r in results[:10]:
        print(
            f"  {r.doc_a} <-> {r.doc_b}: "
            f"{r.overlap_a_in_b * 100:.1f}% of A in B, {r.overlap_b_in_a * 100:.1f}% of B in A"
        )
    print(f"Report written to {args.out.resolve()}")


def run_corpus(args: argparse.Namespace) -> None:
    with Corpus(args.db) as corpus:
        if args.corpus_command == "add":
            for path in args.files:
                if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                    print(f"  skipping {path.name}: unsupported file type")
                    continue
                try:
                    text = extract_text(path)
                except Exception as exc:  # noqa: BLE001 - keep adding remaining files
                    print(f"  skipping {path.name}: {exc}")
                    continue
                doc_id = corpus.add(path.name, text)
                print(f"  added #{doc_id}: {path.name}")
            print(f"Corpus: {args.db.resolve()}")
        elif args.corpus_command == "list":
            docs = corpus.documents()
            if not docs:
                print(f"Corpus is empty: {args.db.resolve()}")
                return
            for d in docs:
                print(f"  #{d.id}  {d.name}  ({d.n_words} words, added {d.added_at})")
        elif args.corpus_command == "remove":
            if corpus.remove(args.doc_id):
                print(f"Removed #{args.doc_id}.")
            else:
                raise SystemExit(f"No document with id {args.doc_id} in {args.db}.")


if __name__ == "__main__":
    main()
