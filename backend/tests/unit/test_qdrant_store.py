import uuid

import pytest
from qdrant_client import QdrantClient, models

from app.domain.documents.models import (
    DocumentChunk,
    ExtractionMethod,
    FileType,
)
from app.infrastructure.vectorstores.qdrant_store import (
    CollectionConfigurationError,
    QdrantVectorStore,
)


def _chunk(document_id: str = "doc-1") -> DocumentChunk:
    return DocumentChunk(
        chunk_id=str(uuid.uuid4()),
        document_id=document_id,
        source_file="sample.txt",
        file_type=FileType.TXT,
        page_number=None,
        chunk_index=0,
        text="IIIT Bhagalpur provides academic programmes.",
        extraction_method=ExtractionMethod.TXT_LOADER,
        metadata={"document_category": "academic_calendar", "chunk_size": 800},
    )


def test_qdrant_local_collection_upsert_verify_search_and_delete() -> None:
    client = QdrantClient(":memory:")
    store = QdrantVectorStore(
        client=client,
        collection_name="unit_test",
        vector_size=4,
        distance="Cosine",
    )
    chunk = _chunk()
    vector = [0.1, 0.2, 0.3, 0.4]

    store.ensure_collection()
    point_ids = store.upsert_chunks(
        chunks=[chunk],
        vectors=[vector],
        embedding_model="test-embedding-model",
        ingestion_job_id="job-1",
    )
    results = store.search(query_vector=vector, top_k=3)

    assert point_ids == [chunk.chunk_id]
    assert len(results) == 1
    assert results[0].text == chunk.text
    assert results[0].source_file == "sample.txt"
    assert results[0].metadata["embedding_model"] == "test-embedding-model"
    assert results[0].metadata["document_category"] == "academic_calendar"
    assert results[0].metadata["chunk_size"] == 800

    store.delete_document("doc-1")
    assert store.search(query_vector=vector, top_k=3) == []
    client.close()


def test_qdrant_supports_existing_named_default_vector_collection() -> None:
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name="named_default",
        vectors_config={"default": models.VectorParams(size=4, distance=models.Distance.COSINE)},
    )
    store = QdrantVectorStore(client, "named_default", vector_size=4)
    chunk = _chunk()
    vector = [0.1, 0.2, 0.3, 0.4]

    point_ids = store.upsert_chunks(
        chunks=[chunk],
        vectors=[vector],
        embedding_model="qwen3-embedding-0.6b",
        ingestion_job_id="job-named",
    )
    results = store.search(vector, top_k=2)

    assert point_ids == [chunk.chunk_id]
    assert len(results) == 1
    assert results[0].text == chunk.text
    client.close()


def test_qdrant_rejects_existing_collection_dimension_mismatch() -> None:
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name="wrong_dimension",
        vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE),
    )
    store = QdrantVectorStore(
        client=client,
        collection_name="wrong_dimension",
        vector_size=4,
    )

    with pytest.raises(CollectionConfigurationError, match="vector size"):
        store.ensure_collection()
    client.close()


def test_qdrant_rejects_mismatched_chunk_and_vector_counts() -> None:
    client = QdrantClient(":memory:")
    store = QdrantVectorStore(client, "count_mismatch", vector_size=4)

    with pytest.raises(ValueError, match="do not match"):
        store.upsert_chunks(
            chunks=[_chunk()],
            vectors=[],
            embedding_model="test",
            ingestion_job_id="job",
        )
    client.close()


def test_search_does_not_create_a_missing_collection() -> None:
    client = QdrantClient(":memory:")
    store = QdrantVectorStore(
        client=client,
        collection_name="not_created",
        vector_size=4,
    )

    assert store.search(query_vector=[0.1, 0.2, 0.3, 0.4]) == []
    assert client.collection_exists("not_created") is False
    client.close()
