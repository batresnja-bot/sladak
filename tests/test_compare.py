from turnitin_diy.compare import build_source, find_matches

COPIED = (
    "Climate policy requires balancing near term economic costs against "
    "long term environmental benefits across multiple generations of stakeholders"
)


def test_detects_verbatim_copy_from_source():
    source = build_source("source-a.txt", COPIED + " and this is unique source filler text padding words")
    target = "Some unrelated intro sentence here. " + COPIED + " Some unrelated outro sentence here."

    words, matches, overlap = find_matches(target, [source], min_run=6)

    assert matches, "expected at least one matched passage"
    assert matches[0].source_id == "source-a.txt"
    assert overlap > 0.3


def test_no_match_for_unrelated_text():
    source = build_source("source-a.txt", COPIED)
    target = "This paragraph shares no meaningful vocabulary overlap with the reference material at all whatsoever"

    _, matches, overlap = find_matches(target, [source], min_run=6)

    assert not matches
    assert overlap == 0


def test_attributes_matches_to_the_right_source_among_several():
    source_a = build_source("a.txt", COPIED + " padding padding padding padding padding padding")
    source_b = build_source("b.txt", "completely different reference text about unrelated botany topics here")
    target = COPIED

    _, matches, _ = find_matches(target, [source_a, source_b], min_run=6)

    assert all(m.source_id == "a.txt" for m in matches)
