from app.core.config import Settings, get_settings
from app.infrastructure.embeddings.local_qwen import LocalQwenEmbeddingClient


def create_embedding_client(
    settings: Settings | None = None,
) -> LocalQwenEmbeddingClient:
    active_settings = settings or get_settings()
    return LocalQwenEmbeddingClient(
        base_url=active_settings.local_embedding_base_url,
        model=active_settings.embedding_model_id,
        expected_dimension=active_settings.embedding_dimension,
    )
