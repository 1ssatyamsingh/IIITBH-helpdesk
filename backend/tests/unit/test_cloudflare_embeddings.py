import numpy as np
import pytest

from app.infrastructure.embeddings.cloudflare_workers_ai import (
    CloudflareEmbeddingClient,
    EmbeddingServiceError,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.headers = {}

    def post(self, url, json):
        self.calls.append((url, json))
        return FakeResponse({"result": {"data": [[0.1, 0.2, 0.3] for _ in json["text"]]}})

    def close(self):
        pass


def test_cloudflare_embeddings_use_account_endpoint_and_validate_dimensions():
    http = FakeHttpClient()
    client = CloudflareEmbeddingClient(
        account_id="account-123",
        api_token="token-abc",
        expected_dimension=3,
        client_factory=lambda **kwargs: http,
    )

    vectors = client.embed_documents(["document one", "document two"])

    assert http.calls[0][0] == "https://api.cloudflare.com/client/v4/accounts/account-123/ai/run/@cf/qwen/qwen3-embedding-0.6b"
    assert http.calls[0][1] == {"text": ["document one", "document two"]}
    assert np.asarray(vectors) == pytest.approx(np.asarray([[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]))


def test_cloudflare_query_embedding_and_model_info():
    http = FakeHttpClient()
    client = CloudflareEmbeddingClient(
        account_id="acct",
        api_token="token",
        expected_dimension=3,
        client_factory=lambda **kwargs: http,
    )

    assert len(client.embed_query("query")) == 3
    assert client.model_info()["dimension"] == 3


def test_cloudflare_rejects_wrong_dimension():
    http = FakeHttpClient()
    client = CloudflareEmbeddingClient(
        account_id="acct",
        api_token="token",
        expected_dimension=4,
        client_factory=lambda **kwargs: http,
    )

    with pytest.raises(EmbeddingServiceError, match="expected shape"):
        client.embed_documents(["text"])


def test_cloudflare_rejects_missing_credentials():
    with pytest.raises(ValueError, match="CLOUDFLARE_ACCOUNT_ID"):
        CloudflareEmbeddingClient(account_id="", api_token="token")
