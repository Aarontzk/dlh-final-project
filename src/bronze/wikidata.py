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

# Bootstrap: allow running this file directly (VS Code Run button), not just via -m
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import config
from logger import get_logger
from setup_buckets import get_minio_client

log = get_logger("bronze_wikidata")

OBJECT_LATEST = "wikidata/latest.json"
CHECKSUM_OBJECT = "checksums/checksums.json"   # registry gabungan, sama dgn BMKG
CHECKSUM_KEY = "wikidata"


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


def _latest_exists(client) -> bool:
    """True if the latest snapshot object is still present in the bucket."""
    try:
        client.stat_object(config.BUCKET_BRONZE, OBJECT_LATEST)
        return True
    except Exception:
        return False


def _load_checksums(client) -> dict[str, str]:
    """Return shared registry {source: md5}, or {} if absent."""
    try:
        obj = client.get_object(config.BUCKET_BRONZE, CHECKSUM_OBJECT)
        return json.loads(obj.read())
    except Exception:
        return {}


def ingest() -> None:
    client = get_minio_client()
    raw = fetch_sparql()

    # checksum over canonical payload: SPARQL has no ORDER BY, so bindings
    # arrive in nondeterministic order. Sort them before hashing, else md5
    # changes every run and idempotency never triggers.
    bindings = raw.get("results", {}).get("bindings", [])
    canonical = sorted(
        json.dumps(b, sort_keys=True, ensure_ascii=False) for b in bindings
    )
    payload_bytes = json.dumps(canonical, ensure_ascii=False).encode("utf-8")
    content_md5 = _md5(payload_bytes)

    checksums = _load_checksums(client)
    if checksums.get(CHECKSUM_KEY) == content_md5 and _latest_exists(client):
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

    # update shared registry, preserve other sources' entries (e.g. BMKG)
    checksums[CHECKSUM_KEY] = content_md5
    reg_body = json.dumps(checksums, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        config.BUCKET_BRONZE, CHECKSUM_OBJECT,
        io.BytesIO(reg_body), length=len(reg_body),
        content_type="application/json",
    )
    log.info("ingestion complete, md5=%s", content_md5)


if __name__ == "__main__":
    ingest()
