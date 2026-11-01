from uuid import uuid4

from app.domain.retrieval.models import (
    EvidenceSource,
    GeneratedAnswer,
    QueryResult,
)
from app.ports.answer_generator import AnswerGenerator
from app.ports.embedding_client import EmbeddingClient
from app.ports.vector_store import VectorStore


class InvalidCitationError(RuntimeError):
    pass


class QueryService:
    """Retrieves source evidence and optionally generates a citation-validated answer."""

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStore,
        answer_generator: AnswerGenerator | None = None,
        embedding_batch_size: int = 16,
        expected_dimension: int = 1024,
    ) -> None:
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.answer_generator = answer_generator
        self.embedding_batch_size = embedding_batch_size
        self.expected_dimension = expected_dimension

    def query(
        self,
        question: str,
        top_k: int = 5,
        score_threshold: float | None = None,
    ) -> QueryResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("Question must not be empty.")
        if top_k < 1 or top_k > 20:
            raise ValueError("top_k must be between 1 and 20.")

        query_vector = self.embedding_client.embed_query(normalized_question)
        if len(query_vector) != self.expected_dimension:
            raise ValueError(
                f"Query embedding dimension {len(query_vector)} does not match "
                f"configured dimension {self.expected_dimension}."
            )

        retrieved = self.vector_store.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        query_id = str(uuid4())
        if not retrieved:
            return QueryResult(
                query_id=query_id,
                status="no_evidence",
                answer=(
                    "I couldn't find relevant evidence in the currently indexed "
                    "IIIT Bhagalpur documents."
                ),
                insufficient_evidence=True,
                sources=[],
            )

        sources = [
            EvidenceSource(
                evidence_id=f"S{index}",
                chunk_id=item.point_id,
                source_file=item.source_file,
                document_id=item.document_id,
                page_number=item.page_number,
                excerpt=item.text,
                score=item.score,
                extraction_method=item.extraction_method,
                metadata=item.metadata,
                source_url=f"/api/v1/knowledge-base/documents/{item.document_id}/file",
            )
            for index, item in enumerate(retrieved, start=1)
        ]

        if self.answer_generator is None:
            return QueryResult(
                query_id=query_id,
                status="evidence_only",
                answer=None,
                insufficient_evidence=False,
                sources=sources,
            )

        generated: GeneratedAnswer = self.answer_generator.generate(
            normalized_question,
            sources,
        )
        valid_ids = {source.evidence_id for source in sources}
        invalid_ids = set(generated.citations) - valid_ids
        if invalid_ids:
            raise InvalidCitationError(
                "Answer model referenced evidence IDs that were not retrieved: "
                + ", ".join(sorted(invalid_ids))
            )
        if not generated.answer.strip() or not generated.citations:
            return QueryResult(
                query_id=query_id,
                status="insufficient_evidence",
                answer=(
                    "The retrieved passages do not provide enough verified evidence "
                    "to answer this question confidently."
                ),
                insufficient_evidence=True,
                sources=sources,
            )

        cited_ids = set(generated.citations)
        cited_sources = [
            source.model_copy(update={"used_in_answer": source.evidence_id in cited_ids})
            for source in sources
        ]
        return QueryResult(
            query_id=query_id,
            status="answered",
            answer=generated.answer,
            insufficient_evidence=False,
            sources=cited_sources,
        )
