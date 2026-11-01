from typing import Any

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    point_id: str
    score: float
    text: str
    document_id: str
    source_file: str
    file_type: str
    page_number: int | None = None
    chunk_index: int
    extraction_method: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceSource(BaseModel):
    evidence_id: str
    chunk_id: str
    source_file: str
    document_id: str = ""
    page_number: int | None = None
    excerpt: str
    score: float
    extraction_method: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_url: str | None = None
    source_type: str = "institutional"
    used_in_answer: bool = False


class GeneratedAnswer(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)


class QueryResult(BaseModel):
    query_id: str
    status: str
    answer: str | None = None
    insufficient_evidence: bool
    sources: list[EvidenceSource]
