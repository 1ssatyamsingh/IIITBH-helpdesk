from collections.abc import Callable

import numpy as np
from huggingface_hub import InferenceClient


class EmbeddingServiceError(RuntimeError):
    pass


class HuggingFaceBgeM3EmbeddingClient:
    """Dense BGE-M3 embeddings through a dedicated Hugging Face Inference Endpoint."""

    MODEL_ID = "BAAI/bge-m3"

    def __init__(
        self,
        endpoint_url: str,
        token: str | None,
        expected_dimension: int = 1024,
        timeout_seconds: float = 120.0,
        inference_client_factory: Callable[..., InferenceClient] = InferenceClient,
    ) -> None:
        if not endpoint_url.strip():
            raise ValueError(
                "HF_EMBEDDING_ENDPOINT_URL is required. Deploy BAAI/bge-m3 "
                "as a Hugging Face Inference Endpoint and configure its URL."
            )
        if expected_dimension <= 0:
            raise ValueError("expected_dimension must be positive")

        self.endpoint_url = endpoint_url.rstrip("/")
        self.expected_dimension = expected_dimension
        self.client = inference_client_factory(
            model=self.endpoint_url,
            token=token,
            timeout=timeout_seconds,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must be non-empty strings.")

        try:
            response = self.client.feature_extraction(
                text=texts,
                normalize=True,
                truncate=True,
            )
        except Exception as exc:
            raise EmbeddingServiceError(
                f"Hugging Face BGE-M3 embedding request failed: {type(exc).__name__}"
            ) from exc

        vectors = np.asarray(response, dtype=np.float32)
        if vectors.ndim == 1 and len(texts) == 1:
            vectors = vectors.reshape(1, -1)

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
            "model_id": self.MODEL_ID,
            "endpoint_url": self.endpoint_url,
            "dimension": self.expected_dimension,
        }
