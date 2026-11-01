from app.domain.documents.models import (
    DocumentExtractionResult,
    ExtractedPage,
    ExtractionMethod,
    ExtractionStatus,
    FileType,
)
from app.infrastructure.chunking.langchain_chunker import LangChainDocumentChunker


def test_chunker_preserves_document_and_page_provenance_metadata():
    extraction = DocumentExtractionResult(
        source_file="BTech_Fee_Structure.pdf",
        file_type=FileType.PDF,
        page_count=1,
        pages=[
            ExtractedPage(
                page_number=1,
                text="Fee schedule details. " * 100,
                classification="digital",
                extraction_method=ExtractionMethod.PYMUPDF,
                extraction_status=ExtractionStatus.SUCCESS,
                extracted_characters=2300,
                metadata={
                    "page_classification": "digital",
                    "pymupdf_version": "test-version",
                },
            )
        ],
        metadata={
            "document_category": "fee_schedule",
            "pdf_classification_rule_version": "pymupdf-page-heuristic-v1",
        },
    )

    chunks = LangChainDocumentChunker(chunk_size=100, chunk_overlap=10).chunk(
        extraction,
        document_id="document-hash",
    )

    assert chunks
    assert chunks[0].metadata["document_category"] == "fee_schedule"
    assert chunks[0].metadata["page_classification"] == "digital"
    assert chunks[0].metadata["pymupdf_version"] == "test-version"
    assert chunks[0].metadata["chunk_size"] == 100
    assert chunks[0].metadata["chunk_overlap"] == 10
