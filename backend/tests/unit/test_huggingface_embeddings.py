import numpy as np
import pytest

from app.infrastructure.embeddings.huggingface_bge_m3 import (
    EmbeddingServiceError,
    HuggingFaceBgeM3EmbeddingClient,
)


class FakeInferenceClient:
    def __init__(self, response: np.ndarray) -> None:
        self.response = response
        self.calls: list[dict] = []

    def feature_extraction(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_bge_m3_embedding_batch_shape_and_query() -> None:
    fake = FakeInferenceClient(np.ones((2, 1024), dtype=np.float32))
    client = HuggingFaceBgeM3EmbeddingClient(
        endpoint_url="https://example.endpoint.test",
        token="test-token",
        inference_client_factory=lambda **_: fake,
    )

    vectors = client.embed_documents(["first document", "second document"])
    fake.response = np.ones((1, 1024), dtype=np.float32)
    query_vector = client.embed_query("query text")

    assert len(vectors) == 2
    assert len(vectors[0]) == 1024
    assert len(query_vector) == 1024
    assert fake.calls[0]["normalize"] is True
    assert fake.calls[0]["truncate"] is True


def test_rejects_missing_endpoint_url() -> None:
    with pytest.raises(ValueError, match="HF_EMBEDDING_ENDPOINT_URL"):
        HuggingFaceBgeM3EmbeddingClient(
            endpoint_url="",
            token=None,
            inference_client_factory=lambda **_: None,
        )


def test_rejects_wrong_embedding_dimension() -> None:
    fake = FakeInferenceClient(np.ones((1, 768), dtype=np.float32))
    client = HuggingFaceBgeM3EmbeddingClient(
        endpoint_url="https://example.endpoint.test",
        token=None,
        inference_client_factory=lambda **_: fake,
    )

    with pytest.raises(EmbeddingServiceError, match="expected shape"):
        client.embed_documents(["one document"])


def test_rejects_non_finite_embeddings() -> None:
    values = np.ones((1, 1024), dtype=np.float32)
    values[0, 0] = np.nan
    fake = FakeInferenceClient(values)
    client = HuggingFaceBgeM3EmbeddingClient(
        endpoint_url="https://example.endpoint.test",
        token=None,
        inference_client_factory=lambda **_: fake,
    )

    with pytest.raises(EmbeddingServiceError, match="non-finite"):
        client.embed_query("query")
