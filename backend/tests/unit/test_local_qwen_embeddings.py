from app.infrastructure.embeddings.local_qwen import LocalQwenEmbeddingClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []

    def post(self, url, json):
        self.calls.append((url, json))
        texts = json["input"]
        # Deliberately return reversed indexes to verify stable ordering.
        data = [
            {"index": index, "embedding": [float(index), 0.0, 0.0]}
            for index in reversed(range(len(texts)))
        ]
        return FakeResponse({"data": data})

    def close(self):
        pass


def test_qwen_documents_are_not_prefixed_and_query_is_instruction_prefixed():
    http = FakeHttpClient()
    client = LocalQwenEmbeddingClient(
        base_url="http://127.0.0.1:8088/",
        expected_dimension=3,
        client_factory=lambda **kwargs: http,
    )

    client.embed_documents(["document text"])
    client.embed_query("What is the fee?")

    assert http.calls[0][0] == "http://127.0.0.1:8088/v1/embeddings"
    assert http.calls[0][1]["input"] == ["document text"]
    assert http.calls[1][1]["input"][0].startswith("Instruct: Given an institutional")
    assert http.calls[1][1]["input"][0].endswith("Query: What is the fee?")


def test_qwen_embedding_dimension_and_response_order():
    http = FakeHttpClient()
    client = LocalQwenEmbeddingClient(
        expected_dimension=3,
        client_factory=lambda **kwargs: http,
    )

    vectors = client.embed_documents(["first", "second"])

    assert vectors == [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
