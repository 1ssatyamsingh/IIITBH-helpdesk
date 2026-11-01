import argparse
import logging
import time

from app.core.config import get_settings
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.workers.ingestion_worker import IngestionWorker


def main() -> None:
    parser = argparse.ArgumentParser(description="IIITBH-RAG ingestion worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued file and exit.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=2.0,
        help="Seconds to wait when no queued files are available.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, get_settings().log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    repository = SQLiteJobRepository(settings.data_dir / "ingestion.sqlite3")
    worker = IngestionWorker(repository=repository, settings=settings)

    if args.once:
        worker.process_next_file()
        return

    logging.getLogger(__name__).info("Ingestion worker started.")
    try:
        while True:
            if not worker.process_next_file():
                time.sleep(max(args.poll_seconds, 0.5))
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Ingestion worker stopped.")


if __name__ == "__main__":
    main()
