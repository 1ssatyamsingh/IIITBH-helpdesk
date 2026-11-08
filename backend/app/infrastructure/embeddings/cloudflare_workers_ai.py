from collections.abc import Callable
from typing import Any

import httpx
import numpy as np


class EmbeddingServiceError(RuntimeError):
    pass


class CloudflareEmbeddingClient:
    """Qwen3 embeddings served by Cloudflare Workers AI REST API."""

    MODEL_ID = "@cf/qwen/qwen3-embedding-0.6b"
    API_BASE_URL = "https://api.cloudflare.com/client/v4"

    def __init__(
        self,
        account_id: str,
        api_token: str,
        expected_dimension: int = 1024,
        model: str = MODEL_ID,
        timeout_seconds: float = 120.0,
        client_factory: Callable[..., Any] = httpx.Client,
    ) -> None:
        if not account_id.strip():
            raise ValueError("CLOUDFLARE_ACCOUNT_ID must not be empty.")
        if not api_token.strip():
            raise ValueError("CLOUDFLARE_API_TOKEN must not be empty.")
        if expected_dimension <= 0:
            raise ValueError("expected_dimension must be positive.")
        self.account_id = account_id.strip()
        self.model = model
        self.expected_dimension = expected_dimension
        self.client = client_factory(timeout=timeout_seconds)
        self.client.headers.update({"Authorization": f"Bearer {api_token}"})

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must be non-empty strings.")
        url = (
            f"{self.API_BASE_URL}/accounts/{self.account_id}/ai/run/{self.model}"
        )
        try:
            response = self.client.post(url, json={"text": texts})
            response.raise_for_status()
            payload = response.json()
            vectors = np.asarray(payload["result"]["data"], dtype=np.float32)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise EmbeddingServiceError(
                f"Cloudflare Workers AI embedding request failed: {type(exc).__name__}"
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

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Query text must not be empty.")
        return self.embed_documents([text])[0]

    def model_info(self) -> dict[str, str | int]:
        return {
            "model_id": self.model,
            "account_id": self.account_id,
            "dimension": self.expected_dimension,
        }

    def close(self) -> None:
        self.client.close()
