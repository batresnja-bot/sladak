from sladak.shingle import shingle_hashes, tokenize, winnow


def test_tokenize_lowercases_and_strips_punctuation():
    assert tokenize("Hello, World! It's 2026.") == ["hello", "world", "it", "s", "2026"]


def test_shingle_hashes_produces_overlapping_windows():
    words = ["a", "b", "c", "d", "e"]
    shingles = shingle_hashes(words, k=3)
    assert len(shingles) == 3
    assert shingles[0].start_word == 0 and shingles[0].end_word == 3
    assert shingles[-1].start_word == 2 and shingles[-1].end_word == 5


def test_shingle_hashes_empty_when_text_shorter_than_k():
    assert shingle_hashes(["a", "b"], k=3) == []


def test_identical_text_has_identical_fingerprints():
    words = tokenize("the quick brown fox jumps over the lazy dog again and again")
    a = winnow(shingle_hashes(words, k=4), window=3)
    b = winnow(shingle_hashes(words, k=4), window=3)
    assert {s.hash for s in a} == {s.hash for s in b}


def test_winnow_shrinks_fingerprint_set():
    words = tokenize(" ".join(f"word{i}" for i in range(200)))
    shingles = shingle_hashes(words, k=6)
    winnowed = winnow(shingles, window=4)
    assert 0 < len(winnowed) < len(shingles)
