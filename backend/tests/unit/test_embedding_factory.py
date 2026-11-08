import pytest

from app.core.config import Settings
from app.infrastructure.embeddings.cloudflare_workers_ai import CloudflareEmbeddingClient
from app.infrastructure.embeddings.factory import create_embedding_client
from app.infrastructure.embeddings.local_qwen import LocalQwenEmbeddingClient


def test_factory_preserves_local_provider_default():
    client = create_embedding_client(Settings(embedding_provider="local"))
    assert isinstance(client, LocalQwenEmbeddingClient)
    client.close()


def test_factory_selects_cloudflare_provider():
    settings = Settings(
        embedding_provider="cloudflare",
        cloudflare_account_id="account-id",
        cloudflare_api_token="api-token",
        cloudflare_embedding_model_id="@cf/qwen/qwen3-embedding-0.6b",
    )
    client = create_embedding_client(settings)
    assert isinstance(client, CloudflareEmbeddingClient)
    assert client.model_info()["model_id"] == "@cf/qwen/qwen3-embedding-0.6b"
    client.close()


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Supported providers: local, cloudflare"):
        create_embedding_client(Settings(embedding_provider="unknown"))
