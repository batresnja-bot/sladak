import io

import pytest

flask = pytest.importorskip("flask")

from turnitin_diy.webapp import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_index_renders_upload_form(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Generate report" in resp.data


def test_analyze_without_document_is_rejected(client):
    resp = client.post("/analyze", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_analyze_rejects_unsupported_extension(client):
    data = {"document": (io.BytesIO(b"hello"), "paper.exe")}
    resp = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_analyze_txt_only_returns_ai_pattern_report(client):
    data = {"document": (io.BytesIO(b"Some short original document text here for testing."), "paper.txt")}
    resp = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert b"Writing-pattern" in resp.data
    assert b"Similarity (text-overlap) match" not in resp.data


def test_analyze_with_sources_returns_similarity_section(client):
    shared = b"Climate policy requires balancing near term economic costs against long term benefits."
    data = {
        "document": (io.BytesIO(b"Intro text. " + shared + b" Outro text."), "paper.txt"),
        "sources": [(io.BytesIO(shared + b" padding padding padding padding padding"), "source.txt")],
    }
    resp = client.post("/analyze", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert b"Similarity (text-overlap) match" in resp.data
