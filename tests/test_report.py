from sladak.ai_detect import analyze_document
from sladak.compare import build_source, find_matches
from sladak.report import combined_report_html, similarity_band

COPIED = (
    "Climate policy requires balancing near term economic costs against "
    "long term environmental benefits across multiple generations of stakeholders"
)


def test_similarity_band_boundaries_match_turnitin():
    assert similarity_band(0.0, has_matches=False)[0] == "blue"
    assert similarity_band(0.10, has_matches=True)[0] == "green"
    assert similarity_band(0.30, has_matches=True)[0] == "yellow"
    assert similarity_band(0.60, has_matches=True)[0] == "orange"
    assert similarity_band(0.90, has_matches=True)[0] == "red"


def test_report_highlights_original_text_with_punctuation():
    source = build_source("src.txt", COPIED + " filler filler filler filler filler")
    target = "An intro, hand-written & idiosyncratic! " + COPIED + " A closing thought."
    result = find_matches(target, [source], min_run=6)
    assert result.matches

    html_out = combined_report_html("t", result, analyze_document(target))

    # The unmatched original text must appear verbatim (escaped), not as
    # lowercase re-joined tokens.
    assert "An intro, hand-written &amp; idiosyncratic!" in html_out
    # And the match block carries the source's number badge.
    assert '<sup class="srcnum">1</sup>' in html_out


def test_report_without_similarity_still_renders_ai_section():
    html_out = combined_report_html(
        "t", None, analyze_document("One sentence here. Another sentence follows. And a third one.")
    )
    assert "Writing-pattern" in html_out
    assert "Similarity (text-overlap) match" not in html_out
