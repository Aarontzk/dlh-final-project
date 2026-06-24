"""Day 1 setup: create MinIO buckets + DuckDB S3 connection helper.

Run: py setup_buckets.py
"""
import os

import duckdb
from minio import Minio

import config
from logger import get_logger

log = get_logger("setup")


def get_minio_client() -> Minio:
    return Minio(
        config.MINIO_ENDPOINT,
        access_key=config.MINIO_ACCESS_KEY,
        secret_key=config.MINIO_SECRET_KEY,
        secure=config.MINIO_SECURE,
    )


def ensure_buckets() -> None:
    client = get_minio_client()
    for bucket in config.BUCKETS:
        if client.bucket_exists(bucket):
            log.info("bucket exists: %s", bucket)
        else:
            client.make_bucket(bucket)
            log.info("bucket created: %s", bucket)


def get_duckdb_connection() -> duckdb.DuckDBPyConnection:
    """DuckDB connection wired to MinIO via httpfs (S3 path-style)."""
    os.makedirs(os.path.dirname(config.DUCKDB_PATH), exist_ok=True)
    con = duckdb.connect(config.DUCKDB_PATH)
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_endpoint='{config.MINIO_ENDPOINT}';")
    con.execute(f"SET s3_access_key_id='{config.MINIO_ACCESS_KEY}';")
    con.execute(f"SET s3_secret_access_key='{config.MINIO_SECRET_KEY}';")
    con.execute("SET s3_use_ssl=false;")
    con.execute("SET s3_url_style='path';")
    return con


def verify() -> None:
    con = get_duckdb_connection()
    ver = con.execute("SELECT version();").fetchone()[0]
    log.info("DuckDB connected: %s", ver)
    con.close()


if __name__ == "__main__":
    log.info("=== Day 1 setup start ===")
    ensure_buckets()
    verify()
    log.info("=== Day 1 setup done ===")
