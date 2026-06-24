"""Gold layer: dim_waktu — datetime dimension from BMKG forecast range.

Generates 3-hour interval timestamps covering a configurable window
(default: 10 days from today). Does NOT depend on Bronze or Silver data.

Writes to:
  - s3://gold/dim_waktu/  (Delta Lake, for versioning)
  - DuckDB table: dim_waktu  (persistent, for query_*.sql)

Run: py -m src.gold.dim_waktu
     py -m src.gold.dim_waktu --start 2026-06-24  (optional override)
"""
import argparse
import os
from datetime import datetime, timedelta

import pandas as pd
from deltalake import DeltaTable, write_deltalake

import config
from logger import get_logger
from setup_buckets import get_duckdb_connection

log = get_logger("gold_dim_waktu")

DELTA_URI = f"s3://{config.BUCKET_GOLD}/dim_waktu"
STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL": f"http://{config.MINIO_ENDPOINT}",
    "AWS_ACCESS_KEY_ID": config.MINIO_ACCESS_KEY,
    "AWS_SECRET_ACCESS_KEY": config.MINIO_SECRET_KEY,
    "AWS_REGION": "us-east-1",
    "AWS_ALLOW_HTTP": "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}

INTERVAL_HOURS = 3
WINDOW_DAYS = 10  # 7-day forecast + 3-day buffer

_HARI = {
    0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis",
    4: "Jumat", 5: "Sabtu", 6: "Minggu",
}


def build_dataframe(start: datetime | None = None) -> pd.DataFrame:
    if start is None:
        today = datetime.now().date()
        start = datetime(today.year, today.month, today.day, 0, 0, 0)

    total_slots = WINDOW_DAYS * (24 // INTERVAL_HOURS)
    rows = []
    for i in range(total_slots):
        dt = start + timedelta(hours=i * INTERVAL_HOURS)
        rows.append({
            "waktu_id":  i + 1,
            "datetime":  dt,
            "tanggal":   dt.strftime("%Y-%m-%d"),
            "jam":       dt.hour,
            "hari":      _HARI[dt.weekday()],
            "bulan":     dt.month,
            "tahun":     dt.year,
        })

    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["waktu_id"] = df["waktu_id"].astype("int32")
    df["jam"]      = df["jam"].astype("int32")
    df["bulan"]    = df["bulan"].astype("int32")
    df["tahun"]    = df["tahun"].astype("int32")
    log.info(
        "built dim_waktu: %d rows  (%s  →  %s)",
        len(df), df["datetime"].min(), df["datetime"].max(),
    )
    return df


def write_delta(df: pd.DataFrame) -> None:
    write_deltalake(
        DELTA_URI, df,
        mode="overwrite",
        storage_options=STORAGE_OPTIONS,
        schema_mode="overwrite",
    )
    dt = DeltaTable(DELTA_URI, storage_options=STORAGE_OPTIONS)
    log.info("wrote Delta %s  version=%d  rows=%d", DELTA_URI, dt.version(), len(df))


def register_duckdb(df: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(config.DUCKDB_PATH), exist_ok=True)
    con = get_duckdb_connection()
    con.register("_dim_waktu_df", df)
    con.execute("CREATE OR REPLACE TABLE dim_waktu AS SELECT * FROM _dim_waktu_df")
    n = con.execute("SELECT COUNT(*) FROM dim_waktu").fetchone()[0]
    con.close()
    log.info("DuckDB table dim_waktu: %d rows", n)


def run(start: datetime | None = None) -> None:
    df = build_dataframe(start)
    write_delta(df)
    register_duckdb(df)
    log.info("dim_waktu done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        default=None,
        help="Start date (YYYY-MM-DD). Default: today midnight.",
    )
    args = parser.parse_args()
    run(args.start)
