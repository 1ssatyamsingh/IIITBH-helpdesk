import argparse
import time
from pathlib import Path

import requests

SUPPORTED = {".txt", ".pdf"}
TERMINAL = {"completed", "completed_with_errors", "blocked", "failed"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit a local TXT/PDF folder to the RAG ingestion API."
    )
    parser.add_argument("--source-dir", default=r"E:\RAG_docs")
    parser.add_argument("--api-base", default="http://127.0.0.1:8018")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--max-file-mb", type=int, default=50)
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--timeout-minutes", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = Path(args.source_dir)
    if not source.is_dir():
        raise SystemExit(f"Source directory does not exist: {source}")
    files = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED)
    too_large = [p for p in files if p.stat().st_size > args.max_file_mb * 1024 * 1024]
    if too_large:
        print("FILES_OVER_LIMIT")
        for path in too_large:
            print(path, round(path.stat().st_size / 1024**2, 2), "MB")
        raise SystemExit("Increase the configured upload limit or handle these files separately.")

    print("SOURCE", source)
    print("FILES_TO_SUBMIT", len(files))
    print("BATCH_SIZE", args.batch_size)
    if args.dry_run:
        for path in files:
            print(path)
        return

    health = requests.get(f"{args.api_base}/api/v1/health", timeout=10)
    health.raise_for_status()
    summaries = []
    for batch_number, start in enumerate(range(0, len(files), args.batch_size), start=1):
        batch = files[start : start + args.batch_size]
        opened = []
        try:
            multipart = []
            for path in batch:
                handle = path.open("rb")
                opened.append(handle)
                mime = "application/pdf" if path.suffix.lower() == ".pdf" else "text/plain"
                multipart.append(("files", (path.name, handle, mime)))
            response = requests.post(
                f"{args.api_base}/api/v1/ingestion/jobs",
                files=multipart,
                timeout=300,
            )
            response.raise_for_status()
            job = response.json()
        finally:
            for handle in opened:
                handle.close()

        job_id = job["job_id"]
        print(f"BATCH {batch_number}: SUBMITTED {len(batch)} FILES JOB {job_id}", flush=True)
        deadline = time.monotonic() + args.timeout_minutes * 60
        while True:
            status_response = requests.get(
                f"{args.api_base}/api/v1/ingestion/jobs/{job_id}",
                timeout=30,
            )
            status_response.raise_for_status()
            current = status_response.json()
            states = {}
            for item in current.get("files", []):
                state = item.get("status", "unknown")
                states[state] = states.get(state, 0) + 1
            print(f"BATCH {batch_number} STATUS {current.get('status')} FILES {states}", flush=True)
            if current.get("status") in TERMINAL:
                summaries.append(
                    {
                        "job_id": job_id,
                        "status": current.get("status"),
                        "files": states,
                        "details": [
                            {
                                "name": f.get("original_filename"),
                                "status": f.get("status"),
                                "error": f.get("error"),
                            }
                            for f in current.get("files", [])
                            if f.get("status") not in {"completed", "completed_with_warnings"}
                        ],
                    }
                )
                break
            if time.monotonic() >= deadline:
                raise SystemExit(f"Timed out waiting for ingestion job {job_id}.")
            time.sleep(args.poll_seconds)

    print("INGESTION_SUMMARY", summaries, flush=True)


if __name__ == "__main__":
    main()
