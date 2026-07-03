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

LLM_FLAVORED_ACADEMIC = (
    "Moreover, the conflict underscores the multifaceted nature of geopolitical risk in the region. "
    "Furthermore, it is important to note that supply chains play a crucial role in transmission. "
    "Additionally, the resulting uncertainty highlights the importance of a comprehensive framework. "
    "Consequently, policymakers must navigate the rapidly evolving landscape of energy markets. "
    "In conclusion, these dynamics have significant implications for the global economy."
)


def test_stock_phrase_heavy_paragraph_scores_higher_than_varied_prose():
    heavy = score_paragraph(STOCK_PHRASE_HEAVY)
    varied = score_paragraph(VARIED_PROSE)
    assert heavy.score > varied.score
    assert heavy.components["stock_phrase_density"] > 0


def test_llm_flavored_academic_prose_lands_in_ai_band():
    result = score_paragraph(LLM_FLAVORED_ACADEMIC)
    assert result.classification == "ai-like"
    assert result.score >= 0.65


def test_varied_personal_prose_lands_in_human_band():
    result = score_paragraph(VARIED_PROSE)
    assert result.classification == "human-like"
    assert result.score < 0.40


def test_short_paragraph_is_not_scored():
    result = score_paragraph("Too short.")
    assert result.classification == "not scored"


def test_analyze_document_fractions_sum_to_one_over_scored_words():
    analysis = analyze_document(LLM_FLAVORED_ACADEMIC + "\n\n" + VARIED_PROSE + "\n\nAbstract")
    assert len(analysis.paragraphs) == 3
    assert analysis.unscored_words > 0  # the "Abstract" heading
    assert abs(analysis.ai_fraction + analysis.mixed_fraction + analysis.human_fraction - 1.0) < 1e-9
    assert analysis.ai_fraction > 0
    assert analysis.human_fraction > 0
    assert 0.0 <= analysis.overall_score <= 1.0


def test_empty_text_returns_no_paragraphs():
    analysis = analyze_document("")
    assert analysis.paragraphs == []
    assert analysis.overall_score == 0.0
    assert analysis.scored_words == 0


def test_split_sentences_does_not_break_on_abbreviations():
    from sladak.ai_detect import split_sentences

    text = (
        "The 2026 Iran-Israel-U.S. war disrupted trade. "
        "Oil prices rose sharply, e.g. Brent crude. "
        "Analysts at the U.S. Federal Reserve responded."
    )
    sentences = split_sentences(text)
    assert len(sentences) == 3
    assert "U.S. war" in sentences[0]
    assert "e.g. Brent" in sentences[1]


def test_bullet_list_items_are_grouped_and_scored():
    bullets = "\n\n".join(
        [
            "The energy channel, operating through crude oil and gas price escalation in futures markets.",
            "The logistics channel, reflecting elevated insurance premiums and rerouting of maritime traffic.",
            "The financial channel, encompassing sanctions fragmentation and repricing of sovereign risk.",
        ]
    )
    analysis = analyze_document(bullets)
    scored = [p for p in analysis.paragraphs if p.classification != "not scored"]
    assert scored, "consecutive short bullet items should be grouped into a scoreable block"
    assert analysis.scored_words > 0


def test_bibliography_excluded_from_ai_analysis():
    body = LLM_FLAVORED_ACADEMIC
    refs = (
        "References\n\n"
        "Caldara, D. and Iacoviello, M. (2022). Measuring geopolitical risk. AER, 112(4).\n"
        "Kilian, L. (2009). Not all oil price shocks are alike. AER, 99(3)."
    )
    analysis = analyze_document(body + "\n\n" + refs)
    assert analysis.bibliography_words > 0
    assert all("Caldara" not in p.text for p in analysis.paragraphs)
