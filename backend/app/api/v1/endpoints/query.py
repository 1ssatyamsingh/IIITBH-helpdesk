import json
from queue import Queue
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_query_service
from app.application.query.query_service import InvalidCitationError, QueryService
from app.infrastructure.answer_generation.openai_compatible_generator import AnswerGenerationError
from app.infrastructure.embeddings.huggingface_bge_m3 import EmbeddingServiceError
from app.infrastructure.vectorstores.qdrant_store import VectorStoreError
from app.schemas.query import QueryRequest, QueryResponse

router = APIRouter(tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Retrieve IIIT Bhagalpur evidence and answer a question",
)
def query_documents(
    request: QueryRequest,
    service: QueryService = Depends(get_query_service),
) -> QueryResponse:
    try:
        result = service.query(
            question=request.question,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
        )
    except InvalidCitationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The answer provider returned an invalid citation reference.",
        ) from exc
    except (AnswerGenerationError, EmbeddingServiceError, VectorStoreError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A retrieval dependency failed. Check backend logs.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return QueryResponse.model_validate(result.model_dump())


@router.post(
    "/query/stream",
    summary="Retrieve institute evidence and stream the answer as server-sent events",
)
def query_documents_stream(
    request: QueryRequest,
    service: QueryService = Depends(get_query_service),
) -> StreamingResponse:
    event_queue: Queue = Queue()

    def run_query():
        try:
            result = service.query(
                question=request.question,
                top_k=request.top_k,
                score_threshold=request.score_threshold,
                on_token=lambda token: event_queue.put({"type": "chunk", "text": token}),
            )
            event_queue.put({"type": "result", "result": result})
        except Exception as exc:
            event_queue.put({"type": "error", "error": exc})
        finally:
            event_queue.put({"type": "worker_done"})

    def events():
        worker = Thread(target=run_query, daemon=True)
        worker.start()
        result = None
        while True:
            event = event_queue.get()
            if event["type"] == "worker_done":
                break
            if event["type"] == "chunk":
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
            elif event["type"] == "result":
                result = event["result"]
            elif event["type"] == "error":
                exc = event["error"]
                yield "data: " + json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n\n"
        if result is not None:
            sources_payload = {
                "type": "sources",
                "sources": [source.model_dump(mode="json") for source in result.sources],
            }
            yield "data: " + json.dumps(sources_payload, ensure_ascii=False) + "\n\n"
            done_payload = {"type": "done", "query_id": result.query_id, "status": result.status}
            yield "data: " + json.dumps(done_payload, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
