"""Bronze ingestion: Wikidata SPARQL (kelurahan/desa Jawa Timur) -> MinIO bronze bucket.

Features:
- Raw JSON stored as-is from SPARQL endpoint
- Idempotency via MD5 checksum (skip if payload unchanged vs latest)
- BX1: custom metadata envelope (ingestion_timestamp, source_api_version, operator_id, content_md5)

Run: py -m src.bronze.wikidata
"""
import hashlib
import io
import json
from datetime import datetime, timezone

import requests

import config
from logger import get_logger
from setup_buckets import get_minio_client

log = get_logger("bronze_wikidata")

OBJECT_LATEST = "wikidata/latest.json"
CHECKSUM_OBJECT = "checksums/wikidata.md5"


def fetch_sparql() -> dict:
    log.info("fetching SPARQL from %s", config.WIKIDATA_SPARQL_ENDPOINT)
    resp = requests.get(
        config.WIKIDATA_SPARQL_ENDPOINT,
        params={"query": config.WIKIDATA_QUERY, "format": "json"},
        headers={"User-Agent": config.WIKIDATA_USER_AGENT, "Accept": "application/sparql-results+json"},
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    n = len(data.get("results", {}).get("bindings", []))
    log.info("SPARQL returned %d rows", n)
    if n == 0:
        raise RuntimeError("SPARQL returned 0 rows - check query/endpoint")
    return data


def _md5(payload: bytes) -> str:
    return hashlib.md5(payload).hexdigest()


def _read_existing_checksum(client) -> str | None:
    try:
        obj = client.get_object(config.BUCKET_BRONZE, CHECKSUM_OBJECT)
        return obj.read().decode("utf-8").strip()
    except Exception:
        return None


def ingest() -> None:
    client = get_minio_client()
    raw = fetch_sparql()

    # checksum only over the actual data payload (stable, excludes our metadata)
    payload_bytes = json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")
    content_md5 = _md5(payload_bytes)

    existing = _read_existing_checksum(client)
    if existing == content_md5:
        log.info("checksum unchanged (%s) - skip ingestion (idempotent)", content_md5)
        return

    # BX1: custom metadata envelope
    envelope = {
        "_metadata": {
            "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_api_version": config.SOURCE_API_VERSION,
            "operator_id": config.OPERATOR_ID,
            "source_endpoint": config.WIKIDATA_SPARQL_ENDPOINT,
            "content_md5": content_md5,
            "row_count": len(raw["results"]["bindings"]),
        },
        "data": raw,
    }
    body = json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")

    # write timestamped snapshot + latest pointer + checksum
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot = f"wikidata/raw_{ts}.json"
    for obj_name in (snapshot, OBJECT_LATEST):
        client.put_object(
            config.BUCKET_BRONZE, obj_name,
            io.BytesIO(body), length=len(body),
            content_type="application/json",
        )
        log.info("wrote s3://%s/%s (%d bytes)", config.BUCKET_BRONZE, obj_name, len(body))

    client.put_object(
        config.BUCKET_BRONZE, CHECKSUM_OBJECT,
        io.BytesIO(content_md5.encode()), length=len(content_md5),
        content_type="text/plain",
    )
    log.info("ingestion complete, md5=%s", content_md5)


if __name__ == "__main__":
    ingest()
