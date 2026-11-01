from app.core.config import Settings, get_settings
from app.infrastructure.answer_generation.openai_compatible_generator import (
    OpenAICompatibleAnswerGenerator,
)


def create_answer_generator(
    settings: Settings | None = None,
) -> OpenAICompatibleAnswerGenerator | None:
    active = settings or get_settings()
    provider = (active.answer_model_provider or "").strip().lower()
    api_key = active.answer_model_api_key
    if provider == "groq" and not api_key:
        # Reuse GROQ_API_KEY for both Groq's scanned-PDF VLM and answer generation.
        api_key = active.groq_api_key
        if not api_key:
            # Keep the API bootable in evidence-only mode until the user adds a key.
            return None

    configured = [active.answer_model_base_url, api_key, active.answer_model_id]
    if not any(configured):
        return None
    if not all(configured):
        raise ValueError(
            "Configure ANSWER_MODEL_BASE_URL, ANSWER_MODEL_ID and the provider API key. "
            "For Groq, GROQ_API_KEY can be reused; otherwise set ANSWER_MODEL_API_KEY."
        )
    return OpenAICompatibleAnswerGenerator(
        base_url=active.answer_model_base_url,
        api_key=api_key,
        model_id=active.answer_model_id,
    )
