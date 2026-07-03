from sladak.compare import build_source, find_matches

COPIED = (
    "Climate policy requires balancing near term economic costs against "
    "long term environmental benefits across multiple generations of stakeholders"
)


def test_detects_verbatim_copy_from_source():
    source = build_source("source-a.txt", COPIED + " and this is unique source filler text padding words")
    target = "Some unrelated intro sentence here. " + COPIED + " Some unrelated outro sentence here."

    result = find_matches(target, [source], min_run=6)

    assert result.matches, "expected at least one matched passage"
    assert result.matches[0].source_id == "source-a.txt"
    assert result.overlap > 0.3


def test_no_match_for_unrelated_text():
    source = build_source("source-a.txt", COPIED)
    target = "This paragraph shares no meaningful vocabulary overlap with the reference material at all whatsoever"

    result = find_matches(target, [source], min_run=6)

    assert not result.matches
    assert result.overlap == 0


def test_attributes_matches_to_the_right_source_among_several():
    source_a = build_source("a.txt", COPIED + " padding padding padding padding padding padding")
    source_b = build_source("b.txt", "completely different reference text about unrelated botany topics here")
    target = COPIED

    result = find_matches(target, [source_a, source_b], min_run=6)

    assert all(m.source_id == "a.txt" for m in result.matches)


def test_result_carries_original_text_and_spans():
    source = build_source("src.txt", COPIED + " filler filler filler filler filler")
    target = "Intro, with punctuation! " + COPIED + " Outro."

    result = find_matches(target, [source], min_run=6)

    assert result.text == target
    assert len(result.word_spans) == len(result.words)
    ws, we = result.word_spans[0]
    assert target[ws:we].lower() == result.words[0]


def test_bridge_gap_merges_lightly_edited_copy_into_one_block():
    # Source passage copied, but a few words replaced in the middle of the target.
    first = (
        "Climate policy requires balancing near term economic costs against "
        "long term environmental benefits for everyone"
    )
    second = (
        "and the resulting policy tradeoffs shape investment decisions made by "
        "governments corporations and individual households alike"
    )
    source = build_source("src.txt", first + " " + second)
    target = first + " SOME TOTALLY EDITED WORDS " + second

    bridged = find_matches(target, [source], min_run=6, bridge_gap=6)
    strict = find_matches(target, [source], min_run=6, bridge_gap=0)

    assert len(bridged.matches) == 1, "edited gap should be bridged into one Turnitin-style block"
    assert len(strict.matches) >= 2, "without bridging the edit should split the match"
    assert bridged.overlap > strict.overlap
