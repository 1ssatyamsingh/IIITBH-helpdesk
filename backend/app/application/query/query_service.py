import re
from datetime import datetime
from uuid import uuid4

from app.application.query.guardrails import validate_question
from app.domain.retrieval.models import EvidenceSource, GeneratedAnswer, QueryResult
from app.ports.answer_generator import AnswerGenerator
from app.ports.embedding_client import EmbeddingClient
from app.ports.vector_store import VectorStore


class InvalidCitationError(RuntimeError):
    pass


CURRENT_PATTERNS = (
    r"\b(current|currently|present|latest|recent|recently|today|now|this year|as of|up to date|updated)\b",
    r"\b(who is|who's)\s+(the\s+)?(director|registrar|dean|hod|head of department|chairperson|chairman)\b",
    r"\b(current|present|new)\s+(director|registrar|dean|hod|head of department|chairperson|chairman)\b",
    r"\b(name of (the )?(director|registrar|dean|hod))\b",
    r"\b(upcoming|next)\s+(event|exam|holiday|deadline|notice|convocation|admission|schedule)\b",
    r"\b(latest|new)\s+(notice|announcement|circular|notification|tender|recruitment)\b",
    r"\b20\d{2}(?:[-–/]\d{2,4})?\b(?!\s*batch\b)",
)


def needs_live_search(question: str) -> bool:
    return any(re.search(pattern, question, re.IGNORECASE) for pattern in CURRENT_PATTERNS)


def rank_retrieved_chunks(question: str, chunks):
    """Reorder dense candidates with topic guards, title relevance and document freshness."""
    normalized = question.casefold()
    is_btech_fee_query = bool(
        re.search(r"b\.?tech|bachelor(?:'s)? of technology", normalized)
        and re.search(r"fee|fees|tuition|cost|payment", normalized)
    )
    if not is_btech_fee_query:
        return sorted(chunks, key=lambda item: item.score, reverse=True)

    ranked = []
    current_year = datetime.now().year
    for item in chunks:
        title = item.source_file.casefold()
        content = item.text.casefold()
        combined = title + " " + content
        if re.search(r"m\.?tech|master of technology|\bph\.?d\.?\b|doctoral fee", title):
            continue
        if not re.search(r"b\.?tech|bachelor(?:'s)? of technology", combined):
            continue

        score = float(item.score)
        if re.search(r"b\.?tech", title) and re.search(r"fee|fees|tuition|structure", title):
            score += 0.12
        years = [int(year) for year in re.findall(r"\b(20\d{2})\b", combined)]
        if years:
            newest_year = max(years)
            score += max(0.0, 0.18 - 0.03 * (current_year - newest_year))
        ranked.append((score, item))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ranked]


class QueryService:
    """Hybrid institutional RAG + live web retrieval with query and answer guardrails."""

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStore,
        answer_generator: AnswerGenerator | None = None,
        embedding_batch_size: int = 16,
        expected_dimension: int = 1024,
        web_search=None,
        web_search_enabled: bool = True,
    ) -> None:
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.answer_generator = answer_generator
        self.embedding_batch_size = embedding_batch_size
        self.expected_dimension = expected_dimension
        self.web_search = web_search
        self.web_search_enabled = web_search_enabled

    def query(
        self, question: str, top_k: int = 5, score_threshold: float | None = None
    ) -> QueryResult:
        normalized_question = validate_question(question)
        if top_k < 1 or top_k > 20:
            raise ValueError("top_k must be between 1 and 20.")

        # Do not spend an extra Groq request rewriting standalone questions. There is no
        # conversation history in this request yet, so rewriting cannot resolve follow-ups.
        retrieval_query = normalized_question

        query_vector = self.embedding_client.embed_query(retrieval_query)
        if len(query_vector) != self.expected_dimension:
            raise ValueError(
                f"Query embedding dimension {len(query_vector)} does not match configured embedding dimension {self.expected_dimension}."
            )
        candidate_k = min(20, max(top_k, top_k * 2))
        candidates = self.vector_store.search(
            query_vector=query_vector, top_k=candidate_k, score_threshold=score_threshold
        )
        retrieved = rank_retrieved_chunks(normalized_question, candidates)[:top_k]
        query_id = str(uuid4())

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
                source_type="institutional",
            )
            for index, item in enumerate(retrieved, start=1)
        ]

        web_error = False
        web_search_attempted = (
            self.web_search_enabled
            and self.web_search is not None
            and needs_live_search(normalized_question)
        )
        if web_search_attempted:
            live_query = retrieval_query + " " + datetime.now().astimezone().date().isoformat()
            try:
                web_results = self.web_search.search(live_query)
                if not web_results:
                    web_error = True
                for index, item in enumerate(web_results, start=1):
                    sources.append(
                        EvidenceSource(
                            evidence_id=f"W{index}",
                            chunk_id="web:" + item["url"],
                            source_file=item["title"],
                            excerpt=item["snippet"],
                            score=1.0,
                            source_url=item["url"],
                            source_type="web",
                            metadata={"domain": item["url"].split("/")[2]},
                        )
                    )
            except Exception:
                # Keep institutional RAG available if a search provider is temporarily down.
                web_error = True

        if not sources:
            note = " Live web search was unavailable." if web_error else ""
            return QueryResult(
                query_id=query_id,
                status="no_evidence",
                answer="I couldn't find relevant evidence in the indexed IIIT Bhagalpur documents or live search."
                + note,
                insufficient_evidence=True,
                sources=[],
            )

        if self.answer_generator is None:
            return QueryResult(
                query_id=query_id,
                status="evidence_only",
                answer=None,
                insufficient_evidence=False,
                sources=sources,
            )

        answer_question = normalized_question
        if web_error:
            answer_question += "\n\nCurrent-information safeguard: live web search returned no usable results or could not be reached. Do not state an office-holder, current notice, deadline, schedule or other time-sensitive fact as verified current. Explicitly say live verification was unavailable and distinguish any dated institute-document evidence."
        generated: GeneratedAnswer = self.answer_generator.generate(answer_question, sources)
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
                answer="The retrieved evidence does not provide enough verified information to answer confidently. Please check the cited official source or contact the institute.",
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
