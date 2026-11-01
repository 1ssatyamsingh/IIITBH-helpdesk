from typing import Protocol

from app.domain.retrieval.models import RetrievedChunk


class VectorStore(Protocol):
    def ensure_collection(self) -> None: ...

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        score_threshold: float | None = None,
    ) -> list[RetrievedChunk]: ...
