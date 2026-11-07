from app.api.v1.endpoints import knowledge_base


class FakeStore:
    def __init__(self, documents):
        self.documents = documents
        self.client = type("Client", (), {"close": lambda self: None})()

    def list_documents(self):
        return self.documents


def test_catalog_returns_first_page_sorted_by_name(monkeypatch):
    knowledge_base._catalog_cache.clear()
    documents = [
        {"document_id": "b", "source_file": "Beta.pdf", "chunk_count": 4, "page_count": 2},
        {"document_id": "a", "source_file": "Alpha.pdf", "chunk_count": 8, "page_count": 3},
        {"document_id": "c", "source_file": "Gamma.pdf", "chunk_count": 1, "page_count": 1},
    ]
    monkeypatch.setattr(knowledge_base, "_store", lambda settings: FakeStore(documents))
    settings = type("Settings", (), {"qdrant_url": "http://fake", "qdrant_collection": "test"})()

    result = knowledge_base.list_knowledge_documents(
        settings=settings, limit=2, offset=0, sort_by="source_file", order="asc"
    )

    assert [item["document_id"] for item in result["documents"]] == ["a", "b"]
    assert result["document_count"] == 3
    assert result["has_more"] is True
    assert result["next_offset"] == 2


def test_catalog_pagination_and_descending_chunk_sort(monkeypatch):
    knowledge_base._catalog_cache.clear()
    documents = [
        {"document_id": "b", "source_file": "Beta.pdf", "chunk_count": 4, "page_count": 2},
        {"document_id": "a", "source_file": "Alpha.pdf", "chunk_count": 8, "page_count": 3},
        {"document_id": "c", "source_file": "Gamma.pdf", "chunk_count": 1, "page_count": 1},
    ]
    monkeypatch.setattr(knowledge_base, "_store", lambda settings: FakeStore(documents))
    settings = type("Settings", (), {"qdrant_url": "http://fake", "qdrant_collection": "test"})()

    result = knowledge_base.list_knowledge_documents(
        settings=settings, limit=2, offset=1, sort_by="chunk_count", order="desc"
    )

    assert [item["document_id"] for item in result["documents"]] == ["b", "c"]
    assert result["has_more"] is False
    assert result["next_offset"] is None


def test_catalog_reuses_server_cache_for_followup_page(monkeypatch):
    knowledge_base._catalog_cache.clear()
    documents = [
        {"document_id": "a", "source_file": "Alpha.pdf", "chunk_count": 2, "page_count": 1},
        {"document_id": "b", "source_file": "Beta.pdf", "chunk_count": 5, "page_count": 2},
    ]
    calls = 0

    def make_store(_settings):
        nonlocal calls
        calls += 1
        return FakeStore(documents)

    monkeypatch.setattr(knowledge_base, "_store", make_store)
    settings = type("Settings", (), {"qdrant_url": "http://fake", "qdrant_collection": "cache"})()

    knowledge_base.list_knowledge_documents(settings=settings, limit=1, offset=0, refresh=False)
    second = knowledge_base.list_knowledge_documents(
        settings=settings, limit=1, offset=1, refresh=False
    )

    assert calls == 1
    assert second["documents"][0]["document_id"] == "b"
    assert second["has_more"] is False
