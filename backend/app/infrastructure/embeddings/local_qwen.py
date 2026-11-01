from collections.abc import Callable
from typing import Any

import httpx
import numpy as np


class EmbeddingServiceError(RuntimeError):
    pass


class LocalQwenEmbeddingClient:
    """Qwen3 embeddings from a loopback llama.cpp OpenAI-compatible server."""

    QUERY_INSTRUCTION = (
        "Instruct: Given an institutional information query, retrieve relevant "
        "passages that answer the query\nQuery: "
    )

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8088",
        model: str = "Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0",
        expected_dimension: int = 1024,
        timeout_seconds: float = 180.0,
        client_factory: Callable[..., Any] = httpx.Client,
    ) -> None:
        if not base_url.strip():
            raise ValueError("LOCAL_EMBEDDING_BASE_URL must not be empty.")
        if expected_dimension <= 0:
            raise ValueError("expected_dimension must be positive.")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.expected_dimension = expected_dimension
        self.client = client_factory(timeout=timeout_seconds)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must be non-empty strings.")
        try:
            response = self.client.post(
                f"{self.base_url}/v1/embeddings",
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
            items = sorted(payload["data"], key=lambda item: item["index"])
            vectors = np.asarray(
                [item["embedding"] for item in items],
                dtype=np.float32,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise EmbeddingServiceError(
                f"Local Qwen embedding request failed: {type(exc).__name__}"
            ) from exc

        expected_shape = (len(texts), self.expected_dimension)
        if vectors.shape != expected_shape:
            raise EmbeddingServiceError(
                f"Embedding response shape {vectors.shape} does not match "
                f"expected shape {expected_shape}."
            )
        if not np.isfinite(vectors).all():
            raise EmbeddingServiceError("Embedding response contains non-finite values.")
        return vectors.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Qwen's retrieval instructions are query-side only.
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Query text must not be empty.")
        return self._embed([f"{self.QUERY_INSTRUCTION}{text.strip()}"])[0]

    def model_info(self) -> dict[str, str | int]:
        return {
            "model_id": self.model,
            "base_url": self.base_url,
            "dimension": self.expected_dimension,
        }

    def close(self) -> None:
        self.client.close()
