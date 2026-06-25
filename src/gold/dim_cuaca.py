"""Gold layer: dim_cuaca — static BMKG weather code dimension.

Does NOT depend on Bronze or Silver data. Populated manually
from official BMKG weather code documentation.

Writes to:
  - s3://gold/dim_cuaca/  (Delta Lake, for versioning)
  - DuckDB table: dim_cuaca  (persistent, for query_*.sql)

Run: py -m src.gold.dim_cuaca
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

log = get_logger("gold_dim_cuaca")

DELTA_URI = f"s3://{config.BUCKET_GOLD}/dim_cuaca"
STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL": f"http://{config.MINIO_ENDPOINT}",
    "AWS_ACCESS_KEY_ID": config.MINIO_ACCESS_KEY,
    "AWS_SECRET_ACCESS_KEY": config.MINIO_SECRET_KEY,
    "AWS_REGION": "us-east-1",
    "AWS_ALLOW_HTTP": "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}

# Manual mapping dari dokumentasi resmi BMKG.
# kategori_risiko: Rendah | Sedang | Tinggi | Ekstrem
_CUACA_ROWS = [
    # cuaca_id, kode_cuaca, deskripsi, kategori_risiko
    (1,  "0",  "Cerah",                 "Rendah"),
    (2,  "1",  "Cerah Berawan",         "Rendah"),
    (3,  "2",  "Cerah Berawan",         "Rendah"),
    (4,  "3",  "Berawan",               "Sedang"),
    (5,  "4",  "Berawan Tebal",         "Sedang"),
    (6,  "5",  "Udara Kabur",           "Sedang"),
    (7,  "10", "Asap",                  "Sedang"),
    (8,  "45", "Berkabut",              "Sedang"),
    (9,  "60", "Hujan Ringan",          "Tinggi"),
    (10, "61", "Hujan Sedang",          "Tinggi"),
    (11, "63", "Hujan Lebat",           "Tinggi"),
    (12, "80", "Hujan Lokal",           "Tinggi"),
    (13, "95", "Hujan Petir",           "Ekstrem"),
    (14, "97", "Hujan Petir Lebat",     "Ekstrem"),
]


def build_dataframe() -> pd.DataFrame:
    df = pd.DataFrame(
        _CUACA_ROWS,
        columns=["cuaca_id", "kode_cuaca", "deskripsi", "kategori_risiko"],
    )
    df["cuaca_id"] = df["cuaca_id"].astype("int32")
    log.info("built dim_cuaca: %d rows", len(df))
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
    con.register("_dim_cuaca_df", df)
    con.execute("CREATE OR REPLACE TABLE dim_cuaca AS SELECT * FROM _dim_cuaca_df")
    n = con.execute("SELECT COUNT(*) FROM dim_cuaca").fetchone()[0]
    con.close()
    log.info("DuckDB table dim_cuaca: %d rows", n)


def run() -> None:
    df = build_dataframe()
    write_delta(df)
    register_duckdb(df)
    log.info("dim_cuaca done")


if __name__ == "__main__":
    run()
