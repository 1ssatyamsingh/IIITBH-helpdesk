import json
from collections import Counter
from pathlib import Path

from app.application.ingestion.process_document import DocumentProcessor
from app.infrastructure.extraction.digital_pdf_extractor import PyMuPDFDocumentExtractor

SOURCE = Path(r"E:\RAG_docs")
SUPPORTED = {".txt", ".pdf"}


def main() -> None:
    if not SOURCE.is_dir():
        raise SystemExit(f"Source directory does not exist: {SOURCE}")
    files = sorted(path for path in SOURCE.rglob("*") if path.is_file())
    supported = [path for path in files if path.suffix.lower() in SUPPORTED]
    skipped = [path for path in files if path.suffix.lower() not in SUPPORTED]
    too_large = [path for path in supported if path.stat().st_size > 50 * 1024 * 1024]

    print("SOURCE", SOURCE)
    print("TOTAL_FILES", len(files))
    print("SUPPORTED_FILES", len(supported))
    print("EXTENSIONS", json.dumps(Counter(p.suffix.lower() for p in supported)))
    print("TOTAL_SUPPORTED_MB", round(sum(p.stat().st_size for p in supported) / 1024**2, 2))
    print("OVER_50_MB", [str(p) for p in too_large])
    print("SKIPPED_NON_TXT_PDF", [str(p) for p in skipped])

    processor = DocumentProcessor(pdf_extractor=PyMuPDFDocumentExtractor())
    totals = Counter()
    errors = []
    for index, path in enumerate(supported, start=1):
        try:
            result = processor.process(path)
            totals["processed_files"] += 1
            totals["chunks"] += len(result.chunks)
            totals["pages"] += result.extraction.page_count
            totals["pages_requiring_vlm"] += len(result.pages_requiring_vlm)
            totals["pages_failed_extraction"] += len(result.pages_failed_extraction)
            totals["empty_chunk_files"] += not bool(result.chunks)
        except Exception as exc:
            errors.append({"file": str(path), "error": type(exc).__name__})
        if index % 10 == 0 or index == len(supported):
            print(f"SCANNED {index}/{len(supported)}")

    print("PREFLIGHT_TOTALS", json.dumps(totals))
    print("PREFLIGHT_ERRORS", json.dumps(errors))
    if too_large or errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
