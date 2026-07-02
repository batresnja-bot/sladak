"""All-pairs comparison of a folder of documents -- the collusion-detection
side of a Turnitin-style workflow, where every submission is checked against
every other submission in the same batch."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .compare import build_source, find_matches
from .extract import SUPPORTED_SUFFIXES, extract_text


@dataclass
class PairResult:
    doc_a: str
    doc_b: str
    overlap_a_in_b: float  # fraction of A's words matched in B
    overlap_b_in_a: float  # fraction of B's words matched in A

    @property
    def max_overlap(self) -> float:
        return max(self.overlap_a_in_b, self.overlap_b_in_a)


def crosscheck_folder(
    folder: Path,
    k: int = 8,
    window: int = 4,
    min_run: int = 8,
) -> list[PairResult]:
    """Compare every document in `folder` against every other, both
    directions, sorted by highest overlap first."""
    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in SUPPORTED_SUFFIXES)
    texts: dict[str, str] = {}
    for path in files:
        try:
            texts[path.name] = extract_text(path)
        except Exception as exc:  # noqa: BLE001 - keep checking remaining files
            print(f"  skipping {path.name}: {exc}")

    names = sorted(texts)
    sources = {name: build_source(name, texts[name], k=k, window=window) for name in names}

    results: list[PairResult] = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            _, _, a_in_b = find_matches(texts[a], [sources[b]], k=k, window=window, min_run=min_run)
            _, _, b_in_a = find_matches(texts[b], [sources[a]], k=k, window=window, min_run=min_run)
            results.append(PairResult(doc_a=a, doc_b=b, overlap_a_in_b=a_in_b, overlap_b_in_a=b_in_a))

    results.sort(key=lambda r: -r.max_overlap)
    return results
