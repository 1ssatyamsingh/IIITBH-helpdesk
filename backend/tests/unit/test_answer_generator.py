from app.domain.retrieval.models import EvidenceSource
from app.infrastructure.answer_generation.openai_compatible_generator import (
    OpenAICompatibleAnswerGenerator,
)


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "The semester begins in July. [S1]"}}]}


class FakeHttp:
    def __init__(self):
        self.payload = None
        self.url = None

    def post(self, url, **kwargs):
        self.url = url
        self.payload = kwargs
        return FakeResponse()


def test_answer_generator_accepts_gpt_oss_full_width_citation_brackets():
    pattern = OpenAICompatibleAnswerGenerator.CITATION_PATTERN
    assert pattern.findall("Supported by source 【S1】 and [S2].") == ["S1", "S2"]


def test_openai_compatible_answer_generator_extracts_citations():
    http = FakeHttp()
    generator = OpenAICompatibleAnswerGenerator(
        base_url="https://api.example.test/v1/",
        api_key="test-key",
        model_id="test-model",
        http_client=http,
    )
    evidence = [
        EvidenceSource(
            evidence_id="S1",
            chunk_id="chunk-1",
            source_file="calendar.pdf",
            page_number=1,
            excerpt="The semester begins in July.",
            score=0.9,
        )
    ]

    result = generator.generate("When does the semester begin?", evidence)

    assert result.citations == ["S1"]
    assert result.answer.endswith("[S1]")
    assert http.url == "https://api.example.test/v1/chat/completions"
    assert http.payload["json"]["model"] == "test-model"
    assert http.payload["json"]["temperature"] == 0.5
    assert http.payload["json"]["reasoning_effort"] == "medium"
    assert http.payload["json"]["include_reasoning"] is False
    assert len(http.payload["json"]["messages"]) == 1
    assert "[S1]" in http.payload["json"]["messages"][0]["content"]
