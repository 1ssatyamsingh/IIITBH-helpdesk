import httpx

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
    assert http.payload["json"]["temperature"] == 0.2
    assert len(http.payload["json"]["messages"]) == 2
    assert http.payload["json"]["messages"][0]["role"] == "system"
    assert "untrusted" in http.payload["json"]["messages"][0]["content"].lower()
    assert "[S1]" in http.payload["json"]["messages"][1]["content"]
    assert OpenAICompatibleAnswerGenerator.CITATION_PATTERN.findall("[W1] [S1]") == ["W1", "S1"]


def test_answer_generator_system_prompt_requires_fresh_official_sources_and_human_followups():
    http = FakeHttp()
    generator = OpenAICompatibleAnswerGenerator(
        base_url="https://api.example.test/v1/",
        api_key="test-key",
        model_id="test-model",
        http_client=http,
    )
    evidence = [
        EvidenceSource(
            evidence_id="W1",
            chunk_id="web:1",
            source_file="Official institute notice",
            excerpt="Current institute detail.",
            score=1.0,
            source_type="web",
            source_url="https://iiitbh.ac.in/notice",
        )
    ]

    generator.generate("Who is the current director?", evidence)

    prompt = http.payload["json"]["messages"][0]["content"].lower()
    assert "newest applicable dated official source" in prompt
    assert "natural, warm, clear and human-friendly voice" in prompt
    assert "ask one concise clarifying follow-up" in prompt
    assert "answer only the question asked" in prompt
    assert "avoid repeating the same facts" in prompt
    assert "prefer a concise answer" in prompt
    assert "default to the newest applicable admission-year document" in prompt
    assert "never use an older-year document as the primary source" in prompt


def test_answer_generator_retries_groq_rate_limit(monkeypatch):
    request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
    limited = httpx.Response(429, headers={"Retry-After": "0"}, request=request)
    rate_limit = httpx.HTTPStatusError("rate limited", request=request, response=limited)

    class RetryHttp:
        def __init__(self):
            self.calls = 0

        def post(self, url, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise rate_limit
            return FakeResponse()

    sleeps = []
    monkeypatch.setattr("app.infrastructure.answer_generation.openai_compatible_generator.time.sleep", sleeps.append)
    http = RetryHttp()
    generator = OpenAICompatibleAnswerGenerator(
        base_url="https://api.example.test/v1",
        api_key="test-key",
        model_id="test-model",
        http_client=http,
    )

    result = generator._complete([{"role": "user", "content": "Hello"}], max_tokens=20)

    assert result == "The semester begins in July. [S1]"
    assert http.calls == 2
    assert sleeps == [0.0]


def test_answer_generator_falls_back_to_cited_source_text_after_http_429(monkeypatch):
    request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
    limited = httpx.Response(429, headers={"Retry-After": "0"}, request=request)
    error = httpx.HTTPStatusError("limited", request=request, response=limited)

    class FailingHttp:
        def post(self, url, **kwargs):
            raise error

    monkeypatch.setattr("app.infrastructure.answer_generation.openai_compatible_generator.time.sleep", lambda _: None)
    generator = OpenAICompatibleAnswerGenerator(
        base_url="https://api.example.test/v1",
        api_key="test-key",
        model_id="test-model",
        http_client=FailingHttp(),
    )
    evidence = [EvidenceSource(
        evidence_id="S1",
        chunk_id="chunk-1",
        source_file="Fee Structure 2026-27 B.Tech.pdf",
        page_number=1,
        excerpt="Tuition fee: INR 144,946 per semester.",
        score=0.9,
    )]

    result = generator.generate("What is the BTech fee?", evidence)

    assert "temporarily rate-limited" in result.answer
    assert "INR 144,946 per semester" in result.answer
    assert result.citations == ["S1"]
