from sladak.ai_detect import analyze_document, score_paragraph

STOCK_PHRASE_HEAVY = (
    "Moreover, it is important to note that climate policy plays a crucial role. "
    "Furthermore, this highlights the significance of long term planning. "
    "In conclusion, this underscores the multifaceted nature of the challenge."
)

VARIED_PROSE = (
    "I still remember the smell of rain on the old porch, sharp and a little metallic. "
    "Dad used to say it meant the crops would be fine this year -- he was wrong more often than right. "
    "We stopped asking after a while."
)


def test_stock_phrase_heavy_paragraph_scores_higher_than_varied_prose():
    heavy = score_paragraph(STOCK_PHRASE_HEAVY)
    varied = score_paragraph(VARIED_PROSE)
    assert heavy.score > varied.score
    assert heavy.components["stock_phrase_density"] > 0


def test_short_paragraph_is_marked_insufficient_text():
    result = score_paragraph("Too short.")
    assert result.confidence == "insufficient text"


def test_analyze_document_overall_score_is_bounded_and_paragraph_count_matches():
    analysis = analyze_document(STOCK_PHRASE_HEAVY + "\n\n" + VARIED_PROSE)
    assert 0.0 <= analysis.overall_score <= 1.0
    assert len(analysis.paragraphs) == 2


def test_empty_text_returns_no_paragraphs():
    analysis = analyze_document("")
    assert analysis.paragraphs == []
    assert analysis.overall_score == 0.0
