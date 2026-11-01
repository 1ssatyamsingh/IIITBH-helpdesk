from app.core.config import Settings
from app.infrastructure.answer_generation.factory import create_answer_generator


def test_answer_generator_factory_returns_none_when_not_configured():
    settings = Settings(
        answer_model_provider=None,
        answer_model_base_url=None,
        answer_model_api_key=None,
        answer_model_id=None,
        groq_api_key=None,
    )
    assert create_answer_generator(settings) is None


def test_groq_answer_generator_stays_in_evidence_only_mode_without_key():
    settings = Settings(
        answer_model_provider="groq",
        answer_model_base_url="https://api.groq.com/openai/v1",
        answer_model_api_key=None,
        answer_model_id="openai/gpt-oss-120b",
        groq_api_key=None,
    )

    assert create_answer_generator(settings) is None


def test_groq_answer_generator_reuses_groq_api_key():
    settings = Settings(
        answer_model_provider="groq",
        answer_model_base_url="https://api.groq.com/openai/v1",
        answer_model_api_key=None,
        answer_model_id="openai/gpt-oss-120b",
        groq_api_key="test-groq-key",
    )

    generator = create_answer_generator(settings)

    assert generator is not None
    assert generator.url == "https://api.groq.com/openai/v1/chat/completions"
    assert generator.api_key == "test-groq-key"
    assert generator.model_id == "openai/gpt-oss-120b"


def test_answer_generator_factory_rejects_partial_configuration():
    settings = Settings(
        answer_model_provider="custom",
        answer_model_base_url="https://api.example.test/v1",
        answer_model_api_key=None,
        answer_model_id="model-name",
        groq_api_key=None,
    )
    try:
        create_answer_generator(settings)
    except ValueError as error:
        assert "Configure ANSWER_MODEL_BASE_URL" in str(error)
    else:
        raise AssertionError("Partial answer model configuration must be rejected.")
