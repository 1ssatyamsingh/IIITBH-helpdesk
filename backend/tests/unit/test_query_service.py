import pytest

from app.application.query.query_service import InvalidCitationError, QueryService
from app.domain.retrieval.models import GeneratedAnswer, RetrievedChunk


class FakeEmbeddingClient:
    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeVectorStore:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self.results = results

    def search(self, query_vector, top_k, score_threshold=None):
        return self.results[:top_k]


class FakeAnswerGenerator:
    def __init__(self, citations: list[str]) -> None:
        self.citations = citations

    def generate(self, question, evidence) -> GeneratedAnswer:
        return GeneratedAnswer(
            answer="The institute offers the programme. [S1]",
            citations=self.citations,
        )


def _retrieved() -> RetrievedChunk:
    return RetrievedChunk(
        point_id="point-1",
        score=0.91,
        text="IIIT Bhagalpur offers B.Tech programmes.",
        document_id="doc-1",
        source_file="programs.txt",
        file_type="txt",
        page_number=None,
        chunk_index=0,
        extraction_method="txt_loader",
        metadata={"ingestion_job_id": "job-1"},
    )


def test_query_returns_evidence_when_answer_model_not_configured() -> None:
    service = QueryService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=FakeVectorStore([_retrieved()]),
        expected_dimension=3,
    )

    result = service.query("Which programmes are offered?")

    assert result.status == "evidence_only"
    assert result.answer is None
    assert result.sources[0].evidence_id == "S1"
    assert result.sources[0].source_file == "programs.txt"
    assert result.sources[0].extraction_method == "txt_loader"


def test_query_returns_no_evidence_without_fabricating_sources() -> None:
    service = QueryService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=FakeVectorStore([]),
        expected_dimension=3,
    )

    result = service.query("What is the campus population?")

    assert result.status == "no_evidence"
    assert result.insufficient_evidence is True
    assert result.sources == []


def test_query_validates_answer_citations() -> None:
    service = QueryService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=FakeVectorStore([_retrieved()]),
        answer_generator=FakeAnswerGenerator(["S9"]),
        expected_dimension=3,
    )

    with pytest.raises(InvalidCitationError):
        service.query("Which programmes are offered?")


def test_query_marks_validated_citations_used_in_answer() -> None:
    service = QueryService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=FakeVectorStore([_retrieved()]),
        answer_generator=FakeAnswerGenerator(["S1"]),
        expected_dimension=3,
    )

    result = service.query("Which programmes are offered?")

    assert result.status == "answered"
    assert result.sources[0].used_in_answer is True
