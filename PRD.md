# Product Requirements Document (PRD)
## IIIT Bhagalpur — Modular RAG Chatbot

**Document status:** Initial product requirements  
**Project folder:** `E:\PROJECT- IIITBH-RAG`  
**Product:** IIITBH-RAG  
**Primary interfaces:** Ingestion and Query  
**Backend:** FastAPI (Python)  
**Frontend:** React  
**Vector database:** Qdrant Cloud  
**Embeddings:** BGE-M3 through the Hugging Face API  
**Document processing:** PyMuPDF and LangChain  
**Scanned-document VLM:** Groq-hosted `qwen/qwen3.8-27b` (preview model; account-level availability and live image requests remain to be verified)

---

## 1. Product vision

Build a modular, production-oriented Retrieval-Augmented Generation (RAG) application for IIIT Bhagalpur information. An authorised user should be able to ingest multiple TXT and PDF documents in one operation, process each file according to its actual content type, store searchable chunks and their provenance in Qdrant Cloud, and ask questions through a simple React interface.

Answers must be grounded in retrieved source material. The system must show evidence and references so that a user can verify where an answer came from. If the indexed sources do not provide sufficient evidence, the system must say so rather than invent an answer.

## 2. Goals

1. Support multi-file upload and ingestion in a single batch.
2. Identify supported file types (TXT and PDF) and route each file to the appropriate processing path.
3. Classify PDFs as digital, scanned, or mixed using PyMuPDF-based text extraction checks.
4. Extract digital PDF text with PyMuPDF.
5. Extract scanned/image-only PDF page content using a Qwen vision-language model through Groq, after confirming the exact supported model identifier and API capabilities.
6. Load TXT files directly and split content with configurable LangChain text splitters.
7. Apply appropriate, configurable chunking and overlap.
8. Generate embeddings using BGE-M3 through the Hugging Face API.
9. Store vectors, text and traceable metadata in Qdrant Cloud.
10. Provide a query interface that retrieves relevant evidence and returns an evidence-grounded answer with citations/references.
11. Keep the codebase modular so ingestion, extraction, chunking, embedding, retrieval and API layers can be tested and replaced independently.

## 3. Non-goals for the first release

- Building a complex admin dashboard or analytics suite.
- Crawling the public institute website automatically.
- Supporting DOCX, XLSX, PPTX, HTML, images or audio as direct ingestion formats.
- Fine-tuning or training an embedding or generative model.
- Building user accounts, role-based access control or multi-tenant workspaces unless later required.
- Automatically modifying or deleting source files.
- Claiming that a document is definitively scanned or digital based only on a heuristic.
- Generating answers from general model knowledge when retrieved evidence is absent.

## 4. Users and primary workflows

### 4.1 Ingestion user

1. Opens the Ingestion page.
2. Selects or uploads multiple TXT and PDF files.
3. Reviews the detected file types and, for PDFs, the detected PDF category.
4. Starts ingestion.
5. Sees per-file progress and final status, including extraction or processing errors.
6. Can inspect the ingestion result and the source metadata stored for each document.

### 4.2 Query user

1. Opens the Query page.
2. Enters a natural-language question.
3. Receives an answer based on retrieved Qdrant evidence.
4. Sees source references for each supported claim, including filename and page number when available.
5. Can inspect the retrieved excerpts used to construct the answer.
6. Receives a clear insufficient-evidence response when retrieval does not support an answer.

## 5. Functional requirements

### 5.1 Ingestion page and batch handling

- The frontend must allow selecting/uploading multiple files in one batch.
- The initial supported extensions are `.txt` and `.pdf` (extension checks must be supplemented by content/type validation where practical).
- The backend must create an ingestion job and track each file independently.
- One failed file must not silently fail or invalidate the processing result of every other file in the batch.
- The UI must show batch-level and per-file states: queued, processing, completed, completed with warnings, or failed.
- The system must report unsupported files and processing failures with actionable messages.
- Original uploaded files must not be modified.
- The system must avoid reporting a file as successfully indexed until its chunks and vectors have been stored and verified in Qdrant.

### 5.2 TXT processing path

1. Validate that the file is a readable text file.
2. Load text using a LangChain-compatible text loader or equivalent loader abstraction.
3. Preserve source filename and available source metadata.
4. Normalize text conservatively (for example, remove invalid control characters); do not remove meaningful content.
5. Pass the loaded document through the configured LangChain text splitter.
6. Preserve chunk order and source metadata.

### 5.3 PDF classification

Use PyMuPDF to inspect each PDF page and extract text statistics. Classification must support three outcomes:

- **DIGITAL:** meaningful extractable text is present across the document.
- **SCANNED:** no meaningful extractable text is found across the document; pages are likely image-based.
- **MIXED:** meaningful text is present on some pages but absent or insufficient on others.

Requirements:
- Classification must be page-aware, not only based on the first page.
- Store the classification result and supporting metrics (page count, pages with meaningful text, average extracted characters per page, and classification rule/version).
- Thresholds must be configurable and documented.
- Treat classification as a routing signal, not guaranteed ground truth. OCR text layers and unusual layouts can affect results.
- Mixed PDFs must be processed page by page: use extracted text for pages with meaningful text and the VLM path for pages that appear image-only, subject to validation.
- A classification result must be visible in the ingestion UI and recorded in the ingestion report.

### 5.4 Digital PDF extraction

- Use PyMuPDF for complete text extraction.
- Extract text page by page.
- Preserve page numbers in metadata.
- Preserve reading order as provided by PyMuPDF; identify extraction anomalies where possible.
- Do not silently discard pages with no extractable text.
- Tables, multi-column layouts, headers and footers may require later specialized handling; the initial implementation must preserve available extracted text and flag known limitations.

### 5.5 Scanned PDF extraction using VLM

- Render scanned PDF pages to images using PyMuPDF.
- Send page images to the configured Qwen vision-language model through the Groq API.
- Extract all legible text and meaningful structure, including headings, paragraphs, lists and tables where possible.
- Keep extraction page-specific and retain the original PDF page number.
- Do not invent missing or illegible text. Mark uncertain or unreadable regions explicitly.
- Capture model/provider errors and retryable failures per page.
- Avoid sending a whole large PDF as one unbounded request; process pages or controlled page batches.
- Store the model identifier, extraction prompt/version, and extraction status in processing metadata.
- **Selected model ID:** `qwen/qwen3.8-27b`. This is listed as a preview model; verify account-level availability, image-input format, image limits, context limits, rate limits and pricing before live ingestion. Do not silently substitute a different model.

### 5.6 Chunking

- Use LangChain text splitters for both TXT and extracted PDF text.
- Chunking must be configurable by document type and/or extraction path.
- Support configurable chunk size and chunk overlap.
- Preserve page and source boundaries in chunk metadata.
- Avoid combining unrelated pages or documents into a chunk.
- Keep table content together where feasible; do not split rows in ways that destroy their meaning.
- Record the splitter type, chunk size, overlap and configuration version used for each ingestion.
- Initial chunk size and overlap are implementation settings to be selected and validated with representative IIITBH documents; they are not fixed by this PRD.

### 5.7 Embedding service

- Use the BGE-M3 embedding model through the Hugging Face API.
- Embedding generation must be encapsulated behind an interface so the provider can be changed without changing ingestion or retrieval business logic.
- Support batch embedding requests where the provider supports them.
- Handle API timeouts, rate limits, transient errors and malformed responses.
- Validate vector dimensions and numeric values before upserting to Qdrant.
- Use the same embedding model and compatible preprocessing for document chunks and user queries.
- Record the embedding model identifier and version/configuration with the collection configuration.
- **Selected model repository:** `BAAI/bge-m3` (dense vector dimension expected to be 1,024). A dedicated Hugging Face Inference Endpoint URL, authentication, endpoint handler/pooling behaviour and actual response shape still require configuration and live verification. Do not assume the generic serverless API serves this model.

### 5.8 Qdrant Cloud storage

- Store embeddings and payload metadata in Qdrant Cloud.
- Keep Qdrant URL, API key and collection name in environment configuration, never in source code or frontend bundles.
- Validate collection vector size and distance metric against the actual BGE-M3 API output before creating or using a collection.
- Store at minimum:
  - `chunk_id`
  - `document_id`
  - `source_file`
  - `file_type`
  - `pdf_classification` (PDFs only)
  - `page_number` (when applicable)
  - `chunk_index`
  - `text`
  - `document_category` (if supplied or reliably assigned)
  - `embedding_model`
  - `ingestion_job_id`
  - `created_at`
- Preserve enough metadata to show citations and trace every retrieved chunk to its source.
- Define and test duplicate/re-ingestion behaviour before enabling production use. Do not silently create duplicate points.
- Verify upsert completion and point counts before marking a document complete.

### 5.9 Query service

- Accept a user question from the React Query page.
- Embed the question using the same BGE-M3 model/configuration used for document chunks.
- Retrieve relevant points from Qdrant.
- Support configurable retrieval parameters such as top-k and score threshold.
- Pass retrieved context to the selected answer-generation model/service. The answer model is Groq-hosted OpenAI GPT-OSS 120B (`openai/gpt-oss-120b`) through Groq's OpenAI-compatible Chat Completions API. The scanned-page VLM remains the separate `qwen/qwen3.8-27b` model. Both use the same `GROQ_API_KEY` by default.
- Require the answer generator to use retrieved context only for institute-specific factual claims.
- If the evidence is missing, contradictory or insufficient, respond explicitly that the indexed documents do not establish the answer.
- Return structured citations linked to retrieved chunks, including source filename, page number (if present), and supporting excerpt.
- Do not fabricate page numbers, source titles, URLs, dates or quotations.
- Return retrieval and generation status separately so failures can be diagnosed.

### 5.10 Query page UI

- Provide a simple chat-style question input and answer display.
- Display citations/references alongside the answer.
- Allow the user to expand a citation to inspect its supporting excerpt and source metadata.
- Show a clear empty state when no documents have been ingested.
- Show loading, no-results, insufficient-evidence and service-error states.
- Keep the interface responsive and accessible.

## 6. Frontend requirements

The frontend should be modern, clean and intentionally simple. It must contain two primary pages only for the first release:

### Ingestion page
- Multi-file upload/selection.
- File list with detected type and PDF classification.
- Start-ingestion action.
- Batch and per-file progress/status.
- Extraction/chunking/indexing summary.
- Clear error and warning display.

### Query page
- Chat-style question interface.
- Evidence-grounded answer.
- Source citations and expandable excerpts.
- Loading, empty, insufficient-evidence and error states.

Navigation between these pages must be obvious. Avoid unnecessary charts, settings screens and decorative complexity in the initial release. Advanced configuration can be managed through backend environment variables initially.

## 7. Backend architecture

Use FastAPI with independent modules/services. Suggested structure:

```text
PROJECT- IIITBH-RAG/
├── PRD.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── ingestion.py
│   │   │       ├── jobs.py
│   │   │       └── query.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   ├── schemas/
│   │   │   ├── ingestion.py
│   │   │   ├── documents.py
│   │   │   └── query.py
│   │   ├── services/
│   │   │   ├── ingestion_service.py
│   │   │   ├── classification_service.py
│   │   │   ├── extraction/
│   │   │   │   ├── txt_extractor.py
│   │   │   │   ├── digital_pdf_extractor.py
│   │   │   │   └── scanned_pdf_vlm_extractor.py
│   │   │   ├── chunking_service.py
│   │   │   ├── embedding_service.py
│   │   │   ├── qdrant_service.py
│   │   │   ├── retrieval_service.py
│   │   │   └── answer_service.py
│   │   └── repositories/
│   │       └── ingestion_job_repository.py
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   └── (React application; implementation structure to be selected)
└── docs/
    └── (architecture and operational documentation)
```

The architecture is a proposal, not a requirement to use these exact filenames. Responsibilities must remain separated:

- **API layer:** HTTP contracts, validation and response serialization.
- **Ingestion orchestration:** coordinates per-file processing and job status.
- **Classification:** determines TXT/PDF and PDF page categories.
- **Extraction adapters:** TXT, digital PDF and scanned PDF/VLM.
- **Chunking:** LangChain splitter configuration and metadata propagation.
- **Embedding adapter:** Hugging Face BGE-M3 API calls.
- **Vector-store adapter:** Qdrant collection management, upsert and retrieval.
- **Query orchestration:** question embedding, retrieval, evidence assembly and answer generation.

## 8. Proposed API contract

The routes below are proposed contracts and may be refined during implementation.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/ingestion/jobs` | Upload multiple files and create an ingestion job |
| GET | `/api/v1/ingestion/jobs/{job_id}` | Get batch and per-file processing status |
| GET | `/api/v1/ingestion/jobs/{job_id}/results` | Get extraction/indexing summary and errors |
| POST | `/api/v1/query` | Ask a question and receive answer plus evidence |
| GET | `/api/v1/health` | Application health check |

API responses must use stable JSON schemas and meaningful HTTP status codes. Long-running ingestion should not require the browser request to remain open; use a job/status pattern. The mechanism for background execution and job persistence must be selected during technical design.

## 9. Security and configuration

- Keep API keys and secrets in backend environment variables or a suitable secret store.
- Never expose Groq, Hugging Face or Qdrant credentials to React.
- Provide a `.env.example` containing variable names and placeholders only.
- Validate file extensions, file signatures where practical, file sizes and PDF readability.
- Use safe temporary-file handling and clean up temporary uploads according to a documented policy.
- Restrict CORS to configured frontend origins.
- Avoid logging API keys, document contents or personal information unnecessarily.
- Define upload limits, retention policy and access controls before deployment.
- Do not include credentials in logs, reports, error messages or source control.

## 10. Reliability, observability and error handling

- Use structured logs with job ID, document ID, page number and processing stage.
- Track durations and status for classification, extraction, chunking, embedding and Qdrant upsert.
- Retry only transient provider/network failures, with bounded retries and backoff.
- Do not endlessly retry invalid files, unsupported models or authentication errors.
- Preserve per-file and per-page error details.
- Make ingestion idempotency and duplicate handling explicit.
- Support graceful handling of partial batch success.
- Add health checks for application availability and dependency connectivity without exposing secrets.

## 11. Acceptance criteria

### Ingestion
- [ ] User can submit multiple TXT and PDF files in one batch.
- [ ] TXT files route to the TXT loader path.
- [ ] PDFs are classified as DIGITAL, SCANNED or MIXED using page-aware PyMuPDF metrics.
- [ ] Digital PDF pages are extracted using PyMuPDF.
- [ ] Scanned PDF pages are rendered and sent to the verified Qwen vision model through Groq.
- [ ] Mixed PDFs route text-bearing and image-only pages appropriately.
- [ ] Extraction output retains source filename and page number.
- [ ] LangChain chunking runs with configurable chunk size and overlap.
- [ ] BGE-M3 embeddings are generated through the configured Hugging Face API.
- [ ] Qdrant upsert is verified before a file is marked completed.
- [ ] A failure in one file is visible and does not hide successful files in the same batch.

### Query
- [ ] User can submit a natural-language question.
- [ ] Query embedding uses the same BGE-M3 configuration as ingestion.
- [ ] Relevant evidence is retrieved from Qdrant.
- [ ] The answer includes references to source file and page where available.
- [ ] The user can inspect supporting excerpts.
- [ ] The service declines to assert unsupported facts when evidence is insufficient.
- [ ] Provider or retrieval failures are reported clearly.

### Frontend
- [ ] Only two primary pages are required: Ingestion and Query.
- [ ] Both pages have loading, empty, success and error states as appropriate.
- [ ] The interface is responsive and usable on common desktop and mobile viewports.

### Quality
- [ ] Unit tests cover PDF classification, extraction routing, chunk metadata and citation mapping.
- [ ] Integration tests cover embedding and Qdrant operations using test configuration.
- [ ] End-to-end test ingests representative TXT, digital PDF, scanned PDF and mixed PDF files, then verifies a query with source evidence.
- [ ] Secrets are not present in frontend bundles or committed source files.

## 12. Testing strategy

Use a small, known test corpus before ingesting the complete institute dataset:

1. A TXT file with known paragraphs.
2. A digital PDF with selectable text.
3. A scanned/image-only PDF.
4. A mixed PDF containing both text-bearing and image-only pages.
5. A PDF with a table (for extraction quality checks).

For each test file, verify:
- classification result and page-level metrics;
- extracted text against the source;
- page-number correctness;
- chunk boundaries and overlap;
- embedding dimensions and response validity;
- Qdrant point count and payload metadata;
- query answer and citation correctness.

Do not use successful API responses alone as proof of extraction quality. Compare extracted content and citations against the original test documents.

## 13. Decisions required before implementation (no assumptions)

The following details are intentionally unresolved. Confirm them rather than silently choosing values:

1. **Groq VLM model:** What exact model ID do you mean by “Qwen 3.8”? Verify the currently available Groq model with image input. Do not substitute another Qwen model without approval.
2. **Answer-generation model:** Selected Groq-hosted OpenAI GPT-OSS 120B (`openai/gpt-oss-120b`), separate from the Groq Qwen VLM used for scanned-page extraction.
3. **Hugging Face API:** Confirm the intended inference API/endpoint and exact BGE-M3 model ID.
4. **Qdrant collection:** Confirm the collection name and whether an existing collection should be reused or a new collection created. Validate vector dimension and distance metric against actual embedding output.
5. **Chunking defaults:** Select chunk size, overlap and splitter after testing representative institute documents.
6. **Retrieval settings:** Select top-k, score threshold and whether reranking is required.
7. **Upload constraints:** Confirm maximum file size, maximum files per batch and allowed PDF page count.
8. **Persistence:** Select how ingestion job state and history should be persisted.
9. **Duplicate policy:** Decide whether re-uploading the same file should skip, replace or create a new document version.
10. **Source references:** Confirm whether citations should link to uploaded files only, original website URLs when available, or both.
11. **Deployment target:** Confirm local-only development first or an intended hosted deployment.
12. **Authentication:** Confirm whether the first release is single-user/local or needs user authentication.

## 14. Delivery phases

### Phase 1 — Foundation
- Establish backend and frontend project skeletons.
- Implement configuration, logging, health endpoint and environment templates.
- Verify connectivity to Hugging Face, Groq and Qdrant using approved credentials.

### Phase 2 — Ingestion pipeline
- Implement multi-file upload and job tracking.
- Implement TXT loading and PyMuPDF PDF classification.
- Implement digital PDF extraction and scanned-page VLM extraction.
- Implement chunking and metadata propagation.
- Implement BGE-M3 embedding and Qdrant upsert.

### Phase 3 — Query pipeline
- Implement question embedding, Qdrant retrieval and evidence assembly.
- Configure and live-verify the Groq GPT-OSS 120B answer-generation integration using `GROQ_API_KEY`; retain citation validation against retrieved evidence.
- Implement evidence-grounded response and citation schema.

### Phase 4 — React interface
- Build the Ingestion and Query pages.
- Connect the pages to FastAPI.
- Add progress, evidence, citation and error states.

### Phase 5 — Validation
- Run representative document tests.
- Verify extraction quality, retrieval relevance and citation accuracy.
- Test partial failures, retries, duplicate handling and secret management.
- Document setup and operation.

## 15. Definition of done

The first release is complete when a user can ingest a batch containing TXT, digital PDF, scanned PDF and mixed PDF files; inspect per-file processing outcomes; retrieve the resulting content through the Query page; and receive evidence-grounded answers with verifiable source references. All external model identifiers, API configurations, chunking defaults and Qdrant settings must be confirmed and recorded. No unresolved integration detail may be silently guessed.
