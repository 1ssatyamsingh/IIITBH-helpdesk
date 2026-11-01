from pydantic import BaseModel, Field

from app.domain.retrieval.models import EvidenceSource


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class QueryResponse(BaseModel):
    query_id: str
    status: str
    answer: str | None = None
    insufficient_evidence: bool
    sources: list[EvidenceSource]
