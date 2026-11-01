from app.domain.documents.models import DocumentChunk
from app.ports.embedding_client import EmbeddingClient


class EmbeddingPipeline:
    """Batches document embedding requests while preserving input order."""

    def __init__(
        self,
        client: EmbeddingClient,
        batch_size: int = 16,
        expected_dimension: int = 1024,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")
        if expected_dimension < 1:
            raise ValueError("expected_dimension must be at least 1.")
        self.client = client
        self.batch_size = batch_size
        self.expected_dimension = expected_dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            batch_vectors = self.client.embed_documents(batch)
            if len(batch_vectors) != len(batch):
                raise ValueError("Embedding provider returned a different vector count.")
            for vector in batch_vectors:
                if len(vector) != self.expected_dimension:
                    raise ValueError(
                        f"Embedding dimension {len(vector)} does not match "
                        f"expected dimension {self.expected_dimension}."
                    )
            vectors.extend(batch_vectors)
        return vectors

    def embed_chunks(self, chunks: list[DocumentChunk]) -> list[list[float]]:
        return self.embed_texts([chunk.text for chunk in chunks])

    def embed_query(self, query: str) -> list[float]:
        vector = self.client.embed_query(query)
        if len(vector) != self.expected_dimension:
            raise ValueError(
                f"Query embedding dimension {len(vector)} does not match "
                f"expected dimension {self.expected_dimension}."
            )
        return vector
