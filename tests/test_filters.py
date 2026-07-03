from sladak.compare import build_source, find_matches
from sladak.filters import bibliography_range, quote_ranges

COPIED = (
    "Climate policy requires balancing near term economic costs against "
    "long term environmental benefits across multiple generations of stakeholders"
)


def test_quote_ranges_straight_and_curly():
    text = 'Before "a quoted bit" middle “another quote” after'
    ranges = quote_ranges(text)
    assert len(ranges) == 2
    assert text[ranges[0][0] : ranges[0][1]] == '"a quoted bit"'
    assert text[ranges[1][0] : ranges[1][1]] == "“another quote”"


def test_unclosed_quote_does_not_exclude_rest_of_document():
    assert quote_ranges('An "unclosed quote runs on and on') == []


def test_bibliography_range_finds_last_heading():
    text = "Body text here.\nReferences\nSmith, J. (2020). A paper."
    r = bibliography_range(text)
    assert r is not None
    assert text[r[0] :].startswith("References")


def test_no_bibliography_heading_returns_none():
    assert bibliography_range("Just body text, no heading anywhere.") is None


def test_exclude_quotes_removes_quoted_match_from_score():
    source = build_source("src.txt", COPIED + " plus unique filler padding words here")
    target = f'Intro sentence for context. "{COPIED}" Outro sentence for context.'

    off = find_matches(target, [source], min_run=6)
    on = find_matches(target, [source], min_run=6, exclude_quotes=True)

    assert off.matches and off.overlap > 0
    assert not on.matches
    assert on.overlap == 0


def test_exclude_bibliography_removes_references_match():
    source = build_source("src.txt", COPIED + " plus unique filler padding words here")
    target = "Original body text that matches nothing at all.\nReferences\n" + COPIED

    off = find_matches(target, [source], min_run=6)
    on = find_matches(target, [source], min_run=6, exclude_bibliography=True)

    assert off.matches
    assert not on.matches
