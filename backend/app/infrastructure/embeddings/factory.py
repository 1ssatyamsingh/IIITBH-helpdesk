from app.core.config import Settings, get_settings
from app.infrastructure.embeddings.cloudflare_workers_ai import CloudflareEmbeddingClient
from app.infrastructure.embeddings.local_qwen import LocalQwenEmbeddingClient
from app.ports.embedding_client import EmbeddingClient


def create_embedding_client(
    settings: Settings | None = None,
) -> EmbeddingClient:
    active_settings = settings or get_settings()
    provider = active_settings.embedding_provider.strip().lower()

    if provider == "local":
        return LocalQwenEmbeddingClient(
            base_url=active_settings.local_embedding_base_url or "",
            model=active_settings.embedding_model_id,
            expected_dimension=active_settings.embedding_dimension,
        )

    if provider == "cloudflare":
        return CloudflareEmbeddingClient(
            account_id=active_settings.cloudflare_account_id or "",
            api_token=active_settings.cloudflare_api_token or "",
            model=active_settings.cloudflare_embedding_model_id,
            expected_dimension=active_settings.embedding_dimension,
        )

    raise ValueError(
        f"Unsupported EMBEDDING_PROVIDER '{active_settings.embedding_provider}'. "
        "Supported providers: local, cloudflare."
    )
