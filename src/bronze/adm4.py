"""Bronze ingestion: local ADM4 BMKG JSON files -> MinIO bronze bucket.

Features:
- Reads all *.json from 'Data ADM4/' folder (8 369 files)
- BX1 metadata envelope per file (ingestion_timestamp, content_md5, adm4_code, source_file)
- Idempotency via per-file MD5: skip upload if checksum matches existing object
- Parallel uploads via ThreadPoolExecutor for throughput
- Manifest written to bmkg/_manifest.json after each run

Run: py -m src.bronze.adm4
"""
import hashlib
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Bootstrap: allow running this file directly (VS Code Run button), not just via -m
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import config
from logger import get_logger
from setup_buckets import get_minio_client

log = get_logger("bronze_adm4")

DATA_DIR = Path("Data ADM4")
BRONZE_PREFIX = "bmkg"
CHECKSUM_OBJECT = "checksums/checksums.json"
MANIFEST_OBJECT = "bmkg/_manifest.json"
MAX_WORKERS = 16
OPERATOR_ID = "fabio"
SOURCE_NAME = "bmkg-adm4-local"


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _load_existing_checksums(client) -> dict[str, str]:
    """Return {adm4_code: md5} from the stored checksum index, or {} if absent."""
    try:
        obj = client.get_object(config.BUCKET_BRONZE, CHECKSUM_OBJECT)
        return json.loads(obj.read().decode("utf-8"))
    except Exception:
        return {}


def _save_checksums(client, checksums: dict[str, str]) -> None:
    body = json.dumps(checksums, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        config.BUCKET_BRONZE, CHECKSUM_OBJECT,
        io.BytesIO(body), length=len(body),
        content_type="application/json",
    )


def _upload_one(client, file_path: Path, existing_checksums: dict[str, str], ts: str) -> tuple[str, str, str]:
    """Upload a single ADM4 file. Returns (adm4_code, md5, status)."""
    adm4_code = file_path.stem  # e.g. '35.01.01.2001'
    raw_bytes = file_path.read_bytes()
    content_md5 = _md5(raw_bytes)

    if existing_checksums.get(adm4_code) == content_md5:
        return adm4_code, content_md5, "skipped"

    raw_data = json.loads(raw_bytes)

    envelope = {
        "_metadata": {
            "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
            "source": SOURCE_NAME,
            "operator_id": OPERATOR_ID,
            "source_file": file_path.name,
            "adm4_code": adm4_code,
            "content_md5": content_md5,
            "ingest_run_ts": ts,
        },
        "data": raw_data,
    }
    body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    obj_name = f"{BRONZE_PREFIX}/{adm4_code}/raw_{ts}.json"

    client.put_object(
        config.BUCKET_BRONZE, obj_name,
        io.BytesIO(body), length=len(body),
        content_type="application/json",
    )
    return adm4_code, content_md5, "uploaded"


def ingest(data_dir: Path = DATA_DIR, max_workers: int = MAX_WORKERS) -> None:
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir.resolve()}")

    files = sorted(data_dir.glob("*.json"))
    if not files:
        raise RuntimeError(f"No JSON files found in {data_dir.resolve()}")
    log.info("found %d ADM4 files in %s", len(files), data_dir)

    client = get_minio_client()
    existing_checksums = _load_existing_checksums(client)
    log.info("loaded %d existing checksums", len(existing_checksums))

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    updated_checksums = dict(existing_checksums)

    uploaded = skipped = failed = 0
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_upload_one, client, f, existing_checksums, ts): f
            for f in files
        }
        for i, future in enumerate(as_completed(futures), 1):
            file_path = futures[future]
            try:
                adm4_code, md5, status = future.result()
                updated_checksums[adm4_code] = md5
                results.append({"adm4_code": adm4_code, "status": status, "md5": md5})
                if status == "uploaded":
                    uploaded += 1
                else:
                    skipped += 1
                if i % 500 == 0 or i == len(files):
                    log.info("progress: %d/%d (uploaded=%d, skipped=%d, failed=%d)",
                             i, len(files), uploaded, skipped, failed)
            except Exception as exc:
                failed += 1
                log.error("failed to upload %s: %s", file_path.name, exc)
                results.append({"adm4_code": file_path.stem, "status": "failed", "error": str(exc)})

    _save_checksums(client, updated_checksums)

    manifest = {
        "run_timestamp": ts,
        "operator_id": OPERATOR_ID,
        "total_files": len(files),
        "uploaded": uploaded,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        config.BUCKET_BRONZE, MANIFEST_OBJECT,
        io.BytesIO(manifest_bytes), length=len(manifest_bytes),
        content_type="application/json",
    )
    log.info("manifest written to s3://%s/%s", config.BUCKET_BRONZE, MANIFEST_OBJECT)
    log.info("ingestion complete: total=%d uploaded=%d skipped=%d failed=%d",
             len(files), uploaded, skipped, failed)
    if failed > 0:
        raise RuntimeError(f"{failed} file(s) failed to upload — check logs for details")


if __name__ == "__main__":
    ingest()
