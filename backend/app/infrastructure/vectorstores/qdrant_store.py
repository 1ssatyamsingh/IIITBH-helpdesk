from qdrant_client import QdrantClient, models

from app.domain.documents.models import DocumentChunk
from app.domain.retrieval.models import RetrievedChunk


class VectorStoreError(RuntimeError):
    pass


class CollectionConfigurationError(VectorStoreError):
    pass


class QdrantVectorStore:
    """Qdrant adapter with strict vector schema checks and verified upserts."""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str,
        vector_size: int = 1024,
        distance: str = "Cosine",
    ) -> None:
        if not collection_name.strip():
            raise ValueError("Qdrant collection name must not be empty.")
        if vector_size <= 0:
            raise ValueError("vector_size must be positive.")
        try:
            self.distance = models.Distance(distance)
        except ValueError as exc:
            raise ValueError(f"Unsupported Qdrant distance metric: {distance}") from exc

        self.client = client
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.vector_name: str | None = None

    @classmethod
    def from_settings(cls, settings) -> "QdrantVectorStore":
        if not settings.qdrant_url:
            raise ValueError("QDRANT_URL is required before connecting to Qdrant Cloud.")
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=180,
        )
        return cls(
            client=client,
            collection_name=settings.qdrant_collection,
            vector_size=settings.embedding_dimension,
            distance=settings.qdrant_distance,
        )

    def _validate_existing_collection(self) -> None:
        info = self.client.get_collection(self.collection_name)
        vectors = info.config.params.vectors
        if isinstance(vectors, models.VectorParams):
            vector_config = vectors
            self.vector_name = None
        elif isinstance(vectors, dict) and set(vectors) == {"default"}:
            vector_config = vectors["default"]
            self.vector_name = "default"
        else:
            raise CollectionConfigurationError(
                "The collection must use one unnamed dense vector or one named 'default' vector."
            )
        if vector_config.size != self.vector_size:
            raise CollectionConfigurationError(
                f"Collection vector size is {vector_config.size}; "
                f"configured embedding dimension is {self.vector_size}."
            )
        if vector_config.distance != self.distance:
            raise CollectionConfigurationError(
                f"Collection distance is {vector_config.distance.value}; "
                f"configured distance is {self.distance.value}."
            )

    def ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "default": models.VectorParams(
                        size=self.vector_size,
                        distance=self.distance,
                    )
                },
            )
            self.vector_name = "default"
            return
        self._validate_existing_collection()

    def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        embedding_model: str,
        ingestion_job_id: str,
    ) -> list[str]:
        if len(chunks) != len(vectors):
            raise ValueError("Chunk count and embedding count do not match.")
        if not chunks:
            return []
        if not embedding_model.strip():
            raise ValueError("embedding_model must be provided.")
        if not ingestion_job_id.strip():
            raise ValueError("ingestion_job_id must be provided.")

        self.ensure_collection()
        points = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            if len(vector) != self.vector_size:
                raise ValueError(
                    f"Vector for chunk {chunk.chunk_id} has dimension {len(vector)}; "
                    f"expected {self.vector_size}."
                )
            payload = chunk.model_dump(mode="json")
            payload.update(
                {
                    "embedding_model": embedding_model,
                    "ingestion_job_id": ingestion_job_id,
                }
            )
            points.append(
                models.PointStruct(
                    id=chunk.chunk_id,
                    vector=(vector if self.vector_name is None else {self.vector_name: vector}),
                    payload=payload,
                )
            )

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
            retrieved = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[point.id for point in points],
                with_payload=False,
                with_vectors=False,
            )
        except Exception as exc:
            raise VectorStoreError(
                f"Qdrant upsert/verification failed: {type(exc).__name__}"
            ) from exc

        retrieved_ids = {str(point.id) for point in retrieved}
        expected_ids = {str(point.id) for point in points}
        if retrieved_ids != expected_ids:
            raise VectorStoreError(
                f"Qdrant verification mismatch: expected {len(expected_ids)} points, "
                f"found {len(retrieved_ids)}."
            )
        return [str(point.id) for point in points]

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        score_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        if len(query_vector) != self.vector_size:
            raise ValueError(
                f"Query vector dimension is {len(query_vector)}; expected {self.vector_size}."
            )
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        if not self.client.collection_exists(self.collection_name):
            return []
        self._validate_existing_collection()
        try:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using=self.vector_name,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            raise VectorStoreError(f"Qdrant search failed: {type(exc).__name__}") from exc

        results = []
        for point in response.points:
            payload = point.payload or {}
            chunk_metadata = payload.get("metadata")
            if not isinstance(chunk_metadata, dict):
                chunk_metadata = {}
            provider_metadata = {
                key: value
                for key, value in payload.items()
                if key
                not in {
                    "text",
                    "document_id",
                    "source_file",
                    "file_type",
                    "page_number",
                    "chunk_index",
                    "extraction_method",
                    "metadata",
                }
            }
            results.append(
                RetrievedChunk(
                    point_id=str(point.id),
                    score=float(point.score),
                    text=str(payload.get("text", "")),
                    document_id=str(payload.get("document_id", "")),
                    source_file=str(payload.get("source_file", "")),
                    file_type=str(payload.get("file_type", "")),
                    page_number=payload.get("page_number"),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    extraction_method=str(payload.get("extraction_method", "")),
                    metadata={**chunk_metadata, **provider_metadata},
                )
            )
        return results

    def list_documents(self) -> list[dict]:
        """Return a deduplicated catalogue of documents represented in the collection."""
        if not self.client.collection_exists(self.collection_name):
            return []
        self._validate_existing_collection()
        documents: dict[str, dict] = {}
        offset = None
        while True:
            points, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                document_id = str(payload.get("document_id") or "")
                source_file = str(payload.get("source_file") or "Unknown document")
                if not document_id:
                    continue
                metadata = payload.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                entry = documents.setdefault(document_id, {
                    "document_id": document_id,
                    "source_file": source_file,
                    "file_type": payload.get("file_type"),
                    "chunk_count": 0,
                    "pages": set(),
                    "metadata": metadata,
                    "ingestion_job_id": payload.get("ingestion_job_id"),
                    "source_url": f"/api/v1/knowledge-base/documents/{document_id}/file",
                })
                entry["chunk_count"] += 1
                page = payload.get("page_number")
                if page is not None:
                    entry["pages"].add(int(page))
            if next_offset is None:
                break
            offset = next_offset
        result = []
        for item in documents.values():
            item["page_count"] = len(item.pop("pages"))
            result.append(item)
        return sorted(result, key=lambda item: item["source_file"].casefold())

    def delete_document(self, document_id: str) -> None:
        if not document_id.strip():
            raise ValueError("document_id must not be empty.")
        if not self.client.collection_exists(self.collection_name):
            return
        self._validate_existing_collection()
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=True,
        )
