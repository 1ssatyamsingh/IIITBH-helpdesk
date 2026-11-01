from uuid import NAMESPACE_URL, uuid5

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.domain.documents.models import (
    DocumentChunk,
    DocumentExtractionResult,
    ExtractionStatus,
)


class LangChainDocumentChunker:
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
            add_start_index=True,
        )

    def chunk(
        self,
        result: DocumentExtractionResult,
        document_id: str,
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        global_index = 0

        for page in result.pages:
            if page.extraction_status != ExtractionStatus.SUCCESS or not page.text.strip():
                continue

            pieces = self.splitter.split_text(page.text)
            for piece in pieces:
                stable_key = f"{document_id}:{page.page_number}:{global_index}:{piece}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=str(uuid5(NAMESPACE_URL, stable_key)),
                        document_id=document_id,
                        source_file=result.source_file,
                        file_type=result.file_type,
                        page_number=page.page_number,
                        chunk_index=global_index,
                        text=piece,
                        extraction_method=page.extraction_method,
                        metadata={
                            **result.metadata,
                            **page.metadata,
                            "chunker": "RecursiveCharacterTextSplitter",
                            "chunk_size": self.chunk_size,
                            "chunk_overlap": self.chunk_overlap,
                            "chunker_config_version": "1",
                        },
                    )
                )
                global_index += 1

        return chunks
