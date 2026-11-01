from app.application.ingestion.embedding_pipeline import EmbeddingPipeline


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(texts)
        return [[float(len(text)), 0.0, 0.0] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 0.0, 0.0]


def test_embedding_pipeline_batches_and_preserves_order() -> None:
    client = FakeEmbeddingClient()
    pipeline = EmbeddingPipeline(
        client=client,
        batch_size=2,
        expected_dimension=3,
    )

    vectors = pipeline.embed_texts(["a", "bb", "ccc", "dddd", "eeeee"])

    assert client.batches == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
    assert vectors == [
        [1.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],
        [3.0, 0.0, 0.0],
        [4.0, 0.0, 0.0],
        [5.0, 0.0, 0.0],
    ]


def test_embedding_pipeline_embeds_query_with_same_client() -> None:
    pipeline = EmbeddingPipeline(FakeEmbeddingClient(), expected_dimension=3)

    assert pipeline.embed_query("hello") == [5.0, 0.0, 0.0]


def test_embedding_pipeline_returns_empty_for_empty_input() -> None:
    pipeline = EmbeddingPipeline(FakeEmbeddingClient(), expected_dimension=3)

    assert pipeline.embed_texts([]) == []
