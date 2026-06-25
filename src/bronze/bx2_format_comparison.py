"""BX2: file format size comparison across layers.

Compares bytes of the same Wikidata dataset across:
- Bronze : raw JSON                (s3://bronze)
- Silver : Parquet                 (s3://silver)
- Silver : Delta Lake (parquet+log)(s3://silver/.../delta)

Run: py -m src.bronze.bx2_format_comparison
"""
import os
import sys

# Allow direct run (python bx2_format_comparison.py): add repo root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Bootstrap: allow running this file directly (VS Code Run button), not just via -m
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import config
from logger import get_logger
from setup_buckets import get_minio_client

log = get_logger("bx2")


def _size(client, bucket: str, prefix: str) -> int:
    return sum(o.size for o in client.list_objects(bucket, prefix=prefix, recursive=True))


def run() -> None:
    c = get_minio_client()
    bronze = _size(c, config.BUCKET_BRONZE, "wikidata/latest.json")
    parquet = _size(c, config.BUCKET_SILVER, "wikidata/data.parquet")
    # Delta table lives under silver/wikidata/ (part files + _delta_log), excluding the standalone parquet
    delta = sum(
        o.size for o in c.list_objects(config.BUCKET_SILVER, prefix="wikidata/", recursive=True)
        if o.object_name != "wikidata/data.parquet"
    )

    log.info("=== BX2 format size comparison (Wikidata ADM4 Jatim) ===")
    base = bronze or 1
    for name, size in (("Bronze JSON (raw)", bronze),
                       ("Silver Parquet", parquet),
                       ("Silver Delta Lake", delta)):
        log.info("%-22s %12d bytes  %8.2f KB  (%.1f%% of Bronze)",
                 name, size, size / 1024, 100 * size / base)
    if parquet:
        log.info("Parquet compression vs JSON: %.1fx smaller", bronze / parquet)


if __name__ == "__main__":
    run()
