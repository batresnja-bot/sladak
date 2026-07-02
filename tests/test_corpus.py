from turnitin_diy.compare import find_matches
from turnitin_diy.corpus import Corpus

COPIED = (
    "Climate policy requires balancing near term economic costs against "
    "long term environmental benefits across multiple generations of stakeholders"
)


def test_add_list_remove_roundtrip(tmp_path):
    with Corpus(tmp_path / "c.db") as corpus:
        doc_id = corpus.add("paper.txt", "some stored document text here")
        docs = corpus.documents()
        assert len(docs) == 1
        assert docs[0].id == doc_id
        assert docs[0].name == "paper.txt"
        assert docs[0].n_words == 5
        assert corpus.remove(doc_id)
        assert corpus.documents() == []
        assert not corpus.remove(doc_id)


def test_corpus_persists_across_reopen(tmp_path):
    db = tmp_path / "c.db"
    with Corpus(db) as corpus:
        corpus.add("a.txt", "first document text")
    with Corpus(db) as corpus:
        assert [d.name for d in corpus.documents()] == ["a.txt"]


def test_check_against_corpus_finds_stored_overlap(tmp_path):
    with Corpus(tmp_path / "c.db") as corpus:
        corpus.add("old_draft.txt", COPIED + " plus unique filler padding words here")
        sources = corpus.build_sources()

    _, matches, overlap = find_matches("Intro. " + COPIED + " Outro.", sources, min_run=6)
    assert matches
    assert matches[0].source_id.startswith("corpus #")
    assert "old_draft.txt" in matches[0].source_id
    assert overlap > 0
