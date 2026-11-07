import pytest

from app.application.query.query_service import InvalidCitationError, QueryService, needs_live_search, rank_retrieved_chunks
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


def test_live_search_is_triggered_for_year_specific_institute_questions() -> None:
    assert needs_live_search("Show the academic calendar for 2026–27") is True
    assert needs_live_search("What is the B.Tech fee structure?") is False


def test_live_search_is_triggered_for_current_director_questions() -> None:
    assert needs_live_search("Who is the director?") is True
    assert needs_live_search("Who was the director in 2020?") is True


def test_btech_fee_retrieval_prefers_latest_matching_year_and_excludes_other_programmes() -> None:
    legacy = _retrieved().model_copy(update={
        "point_id": "legacy-fee",
        "score": 0.82,
        "source_file": "Document__BTech_Fee_Structure.pdf",
        "text": "B.Tech tuition fee and fee structure for students admitted after 2019.",
    })
    latest = _retrieved().model_copy(update={
        "point_id": "latest-fee",
        "score": 0.70,
        "source_file": "Fee Structure 2026-27 B.Tech.pdf",
        "text": "B.Tech fee structure for 2026 admission through JoSAA and CSAB.",
    })
    wrong_programme = _retrieved().model_copy(update={
        "point_id": "mtech-fee",
        "score": 0.78,
        "source_file": "MTech Fees Structure.txt",
        "text": "M.Tech tuition fee and semester fees.",
    })

    ranked = rank_retrieved_chunks("What are the BTech fee details?", [legacy, wrong_programme, latest])

    assert [item.point_id for item in ranked] == ["latest-fee", "legacy-fee"]


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
