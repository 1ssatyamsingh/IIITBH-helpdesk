import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACTIVE_FILE_STATUSES = {
    "received",
    "validating",
    "classifying",
    "extracting",
    "chunking",
    "embedding",
    "indexing",
}
SUCCESS_FILE_STATUSES = {"completed", "completed_with_warnings"}
TERMINAL_FILE_STATUSES = SUCCESS_FILE_STATUSES | {"failed", "rejected", "blocked"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteJobRepository:
    """Durable local SQLite store for ingestion jobs and per-file processing state."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ingestion_files (
                    file_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    storage_path TEXT,
                    file_type TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES ingestion_jobs(job_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_ingestion_files_status_created
                    ON ingestion_files(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_ingestion_files_job
                    ON ingestion_files(job_id);
                """
            )

    def create_job(self, job_id: str, files: list[dict[str, Any]]) -> None:
        if not files:
            raise ValueError("An ingestion job must contain at least one file.")
        timestamp = _now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO ingestion_jobs(job_id, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (job_id, "queued", timestamp, timestamp),
            )
            for file in files:
                connection.execute(
                    """
                    INSERT INTO ingestion_files(
                        file_id, job_id, original_filename, storage_path, file_type,
                        status, error, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file["file_id"],
                        job_id,
                        file["original_filename"],
                        file.get("storage_path"),
                        file.get("file_type"),
                        file.get("status", "received"),
                        file.get("error"),
                        json.dumps(file.get("metadata", {}), ensure_ascii=False),
                        timestamp,
                        timestamp,
                    ),
                )
            self._refresh_job_status(connection, job_id)

    def claim_next_file(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM ingestion_files
                WHERE status = 'received'
                ORDER BY created_at, file_id
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None

            timestamp = _now()
            connection.execute(
                "UPDATE ingestion_files SET status = 'validating', updated_at = ? "
                "WHERE file_id = ? AND status = 'received'",
                (timestamp, row["file_id"]),
            )
            connection.execute(
                "UPDATE ingestion_jobs SET status = 'processing', updated_at = ? WHERE job_id = ?",
                (timestamp, row["job_id"]),
            )
            claimed = dict(row)
            claimed["status"] = "validating"
            claimed["metadata"] = json.loads(claimed.pop("metadata_json") or "{}")
            return claimed

    def update_file(
        self,
        file_id: str,
        status: str,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        timestamp = _now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT job_id, metadata_json FROM ingestion_files WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown ingestion file ID: {file_id}")

            merged_metadata = json.loads(row["metadata_json"] or "{}")
            if metadata:
                merged_metadata.update(metadata)
            connection.execute(
                """
                UPDATE ingestion_files
                SET status = ?, error = ?, metadata_json = ?, updated_at = ?
                WHERE file_id = ?
                """,
                (
                    status,
                    error,
                    json.dumps(merged_metadata, ensure_ascii=False),
                    timestamp,
                    file_id,
                ),
            )
            self._refresh_job_status(connection, row["job_id"])

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            job = connection.execute(
                "SELECT * FROM ingestion_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if job is None:
                return None

            files = connection.execute(
                "SELECT * FROM ingestion_files WHERE job_id = ? ORDER BY created_at, file_id",
                (job_id,),
            ).fetchall()

        return {
            **dict(job),
            "files": [
                {
                    **{key: value for key, value in dict(file).items() if key != "metadata_json"},
                    "metadata": json.loads(file["metadata_json"] or "{}"),
                }
                for file in files
            ],
        }

    @staticmethod
    def _refresh_job_status(connection: sqlite3.Connection, job_id: str) -> None:
        rows = connection.execute(
            "SELECT status FROM ingestion_files WHERE job_id = ?", (job_id,)
        ).fetchall()
        statuses = [row["status"] for row in rows]
        if not statuses:
            job_status = "failed"
        elif any(status in ACTIVE_FILE_STATUSES - {"received"} for status in statuses):
            job_status = "processing"
        elif any(status == "received" for status in statuses):
            job_status = "queued"
        elif all(status in SUCCESS_FILE_STATUSES for status in statuses):
            job_status = "completed"
        elif any(status in SUCCESS_FILE_STATUSES for status in statuses):
            job_status = "completed_with_errors"
        elif any(status == "blocked" for status in statuses):
            job_status = "blocked"
        else:
            job_status = "failed"

        connection.execute(
            "UPDATE ingestion_jobs SET status = ?, updated_at = ? WHERE job_id = ?",
            (job_status, _now(), job_id),
        )

    def retry_file(self, job_id: str, file_id: str) -> None:
        """Requeue a failed/blocked file without changing its uploaded source bytes."""
        timestamp = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT job_id, status FROM ingestion_files WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            if row is None or row["job_id"] != job_id:
                raise KeyError(f"Unknown file {file_id} in ingestion job {job_id}.")
            if row["status"] not in {"failed", "blocked"}:
                raise ValueError(
                    "Only failed or blocked files can be retried; "
                    f"current status is {row['status']}."
                )
            connection.execute(
                """
                UPDATE ingestion_files
                SET status = 'received', error = NULL, updated_at = ?
                WHERE file_id = ?
                """,
                (timestamp, file_id),
            )
            self._refresh_job_status(connection, job_id)
