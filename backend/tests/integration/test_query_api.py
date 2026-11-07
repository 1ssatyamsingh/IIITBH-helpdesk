import json

from fastapi.testclient import TestClient

from app.api.dependencies import get_query_service
from app.core.config import Settings, get_settings
from app.domain.retrieval.models import EvidenceSource, QueryResult
from app.main import app


class FakeQueryService:
    def query(self, question: str, top_k: int, score_threshold=None) -> QueryResult:
        return QueryResult(
            query_id="query-test",
            status="evidence_only",
            answer=None,
            insufficient_evidence=False,
            sources=[
                EvidenceSource(
                    evidence_id="S1",
                    chunk_id="chunk-1",
                    source_file="academic-calendar.pdf",
                    page_number=1,
                    excerpt="Academic calendar excerpt",
                    score=0.88,
                )
            ],
        )


def test_query_api_returns_evidence_sources() -> None:
    app.dependency_overrides[get_query_service] = lambda: FakeQueryService()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/query",
            json={"question": "When does the semester begin?", "top_k": 5},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "evidence_only"
        assert body["sources"][0]["source_file"] == "academic-calendar.pdf"
        assert body["sources"][0]["page_number"] == 1
    finally:
        app.dependency_overrides.clear()


def test_query_stream_endpoint_emits_answer_chunks_and_sources() -> None:
    class AnsweredQueryService:
        def query(self, question: str, top_k: int, score_threshold=None, on_token=None) -> QueryResult:
            answer = "Fee is INR 10,000 per semester. [S1]"
            if on_token:
                on_token("Fee is INR 10,000 ")
                on_token("per semester. [S1]")
            return QueryResult(
                query_id="stream-test",
                status="answered",
                answer=answer,
                insufficient_evidence=False,
                sources=[EvidenceSource(
                    evidence_id="S1", chunk_id="chunk-1", source_file="fees.pdf",
                    page_number=1, excerpt="Fee is INR 10,000 per semester.", score=0.9,
                )],
            )

    app.dependency_overrides[get_query_service] = lambda: AnsweredQueryService()
    client = TestClient(app)
    try:
        response = client.post("/api/v1/query/stream", json={"question": "What is the fee?", "top_k": 5})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        assert any(event["type"] == "chunk" and event["text"] for event in events)
        assert any(event["type"] == "sources" and event["sources"][0]["evidence_id"] == "S1" for event in events)
        assert events[-1]["type"] == "done"
    finally:
        app.dependency_overrides.clear()


def test_query_api_reports_missing_provider_configuration() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        local_embedding_base_url=None,
        qdrant_url=None,
    )
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/query",
            json={"question": "What are the admission requirements?"},
        )

        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()
