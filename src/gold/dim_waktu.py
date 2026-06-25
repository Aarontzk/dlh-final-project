"""Gold layer: dim_waktu — datetime dimension dari slot aktual Silver BMKG.

Mengekstrak unique local_datetime dari Silver BMKG sehingga setiap slot
forecast BMKG memiliki waktu_id yang cocok di fact table.

Depends on:
  - Silver BMKG Delta table  (src/silver/bmkg.py must run first)

Writes to:
  - s3://gold/dim_waktu/  (Delta Lake, for versioning)
  - DuckDB table: dim_waktu  (persistent, for query_*.sql)

Run: py -m src.gold.dim_waktu
"""
import os

import pandas as pd
from deltalake import DeltaTable, write_deltalake

# Bootstrap: allow running this file directly (VS Code Run button), not just via -m
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import config
from logger import get_logger
from setup_buckets import get_duckdb_connection

log = get_logger("gold_dim_waktu")

SILVER_BMKG_DELTA_URI = f"s3://{config.BUCKET_SILVER}/bmkg"
DELTA_URI             = f"s3://{config.BUCKET_GOLD}/dim_waktu"

STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL":           f"http://{config.MINIO_ENDPOINT}",
    "AWS_ACCESS_KEY_ID":          config.MINIO_ACCESS_KEY,
    "AWS_SECRET_ACCESS_KEY":      config.MINIO_SECRET_KEY,
    "AWS_REGION":                 "us-east-1",
    "AWS_ALLOW_HTTP":             "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}

_HARI = {
    0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis",
    4: "Jumat", 5: "Sabtu", 6: "Minggu",
}


def build_dataframe() -> pd.DataFrame:
    """Ekstrak unique forecast timestamps dari Silver BMKG local_datetime."""
    dt = DeltaTable(SILVER_BMKG_DELTA_URI, storage_options=STORAGE_OPTIONS)
    src = dt.to_pandas(columns=["local_datetime"])

    unique_dts = (
        pd.to_datetime(src["local_datetime"].dropna(), errors="coerce")
          .dropna()
          .drop_duplicates()
          .sort_values()
          .reset_index(drop=True)
    )

    rows = []
    for i, ts in enumerate(unique_dts):
        rows.append({
            "waktu_id": i + 1,
            "datetime":  ts,
            "tanggal":   ts.strftime("%Y-%m-%d"),
            "jam":       ts.hour,
            "hari":      _HARI[ts.weekday()],
            "bulan":     ts.month,
            "tahun":     ts.year,
        })

    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["waktu_id"] = df["waktu_id"].astype("int32")
    df["jam"]      = df["jam"].astype("int32")
    df["bulan"]    = df["bulan"].astype("int32")
    df["tahun"]    = df["tahun"].astype("int32")

    log.info(
        "built dim_waktu: %d unique slots  (%s → %s)",
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


def run() -> None:
    df = build_dataframe()
    write_delta(df)
    register_duckdb(df)
    log.info("dim_waktu done")


if __name__ == "__main__":
    run()
