from turnitin_diy.compare import summarize_by_source
from turnitin_diy.crosscheck import crosscheck_folder

SHARED = (
    "Climate policy requires balancing near term economic costs against "
    "long term environmental benefits across multiple generations of stakeholders. "
)


def test_crosscheck_ranks_colluding_pair_first(tmp_path):
    (tmp_path / "alice.txt").write_text("My intro. " + SHARED + "My outro.")
    (tmp_path / "bob.txt").write_text("Different intro. " + SHARED + "Different outro.")
    (tmp_path / "carol.txt").write_text(
        "Entirely unrelated essay about medieval falconry techniques and their "
        "social history in fourteenth century Europe, nothing shared at all."
    )

    results = crosscheck_folder(tmp_path, min_run=6)

    assert len(results) == 3  # 3 unordered pairs
    top = results[0]
    assert {top.doc_a, top.doc_b} == {"alice.txt", "bob.txt"}
    assert top.max_overlap > 0.3
    assert all(r.max_overlap == 0 for r in results[1:])


def test_summarize_by_source_orders_and_bounds_fractions():
    from turnitin_diy.compare import Match

    matches = [
        Match(source_id="big.txt", target_start=0, target_end=10, source_start=0, source_end=10),
        Match(source_id="small.txt", target_start=12, target_end=15, source_start=0, source_end=3),
    ]
    breakdown = summarize_by_source(20, matches)
    assert breakdown[0] == ("big.txt", 0.5)
    assert breakdown[1] == ("small.txt", 3 / 20)
