from app.api.dependencies import _cached_query_service, close_cached_query_services
from app.core.config import Settings


def test_query_service_is_reused_for_identical_settings() -> None:
    settings = Settings(
        local_embedding_base_url="http://127.0.0.1:8088",
        qdrant_url="http://localhost:6333",
        qdrant_api_key=None,
        qdrant_collection="cache_test",
        answer_model_provider="groq",
        answer_model_base_url="https://api.groq.com/openai/v1",
        answer_model_id="test-model",
        answer_model_api_key="test-key",
    )
    settings_json = settings.model_dump_json()
    _cached_query_service.cache_clear()

    first = _cached_query_service(settings_json)
    second = _cached_query_service(settings_json)

    assert first is second
    close_cached_query_services()
