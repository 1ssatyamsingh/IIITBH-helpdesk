from qdrant_client import QdrantClient, models

from app.infrastructure.vectorstores.qdrant_store import QdrantVectorStore


def test_delete_document_removes_only_matching_document_points():
    client = QdrantClient(":memory:")
    store = QdrantVectorStore(client, "test_docs", vector_size=3)
    store.ensure_collection()
    points = [
        models.PointStruct(
            id="00000000-0000-0000-0000-000000000001",
            vector={"default": [1.0, 0.0, 0.0]},
            payload={"document_id": "doc-a", "text": "a1"},
        ),
        models.PointStruct(
            id="00000000-0000-0000-0000-000000000002",
            vector={"default": [0.9, 0.1, 0.0]},
            payload={"document_id": "doc-a", "text": "a2"},
        ),
        models.PointStruct(
            id="00000000-0000-0000-0000-000000000003",
            vector={"default": [0.0, 1.0, 0.0]},
            payload={"document_id": "doc-b", "text": "b1"},
        ),
    ]
    client.upsert(collection_name="test_docs", points=points, wait=True)

    deleted = store.delete_document("doc-a")

    assert deleted == 2
    remaining, _ = client.scroll(collection_name="test_docs", limit=10, with_payload=True)
    assert [point.payload["document_id"] for point in remaining] == ["doc-b"]
    client.close()
