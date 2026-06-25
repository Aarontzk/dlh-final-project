"""Gold layer: fact_prakiraan_cuaca — central fact table (Star Schema).

Depends on:
  - DuckDB table: dim_wilayah    (dim_wilayah.py must run first)
  - DuckDB table: dim_cuaca      (dim_cuaca.py must run first)
  - DuckDB table: dim_waktu      (dim_waktu.py must run first)
  - Silver BMKG Delta table      (src/silver/bmkg.py must run first)

Writes to:
  - s3://gold/fact_prakiraan_cuaca/  (Delta Lake)
  - DuckDB table: fact_prakiraan_cuaca

Run: py -m src.gold.fact_prakiraan
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

log = get_logger("gold_fact_prakiraan")

SILVER_BMKG_DELTA_URI = f"s3://{config.BUCKET_SILVER}/bmkg"

DELTA_URI = f"s3://{config.BUCKET_GOLD}/fact_prakiraan_cuaca"
STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL": f"http://{config.MINIO_ENDPOINT}",
    "AWS_ACCESS_KEY_ID": config.MINIO_ACCESS_KEY,
    "AWS_SECRET_ACCESS_KEY": config.MINIO_SECRET_KEY,
    "AWS_REGION": "us-east-1",
    "AWS_ALLOW_HTTP": "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}

# Kolom Silver BMKG (confirmed dari src/silver/bmkg.py)
COL_ADM4       = "adm4"           # kode wilayah ADM4 → join key ke dim_wilayah
COL_DATETIME   = "local_datetime" # timestamp WIB (naive) → join key ke dim_waktu
COL_CUACA      = "weather"        # kode cuaca integer → join key ke dim_cuaca.kode_cuaca
COL_SUHU       = "t"              # suhu prakiraan (°C) — BMKG menyediakan satu nilai per slot
COL_KELEMBABAN = "hu"             # kelembaban relatif (%)
COL_ANGIN_KEC  = "ws"             # kecepatan angin (m/s)
COL_ANGIN_ARAH = "wd"             # arah angin (N, S, NE, ...)


def load_silver_bmkg() -> pd.DataFrame:
    dt = DeltaTable(SILVER_BMKG_DELTA_URI, storage_options=STORAGE_OPTIONS)
    df = dt.to_pandas()
    log.info("loaded Silver BMKG: %d rows, columns: %s", len(df), list(df.columns))
    return df


def load_dim_lookups(con) -> tuple[dict, dict, dict]:
    """Return lookup dicts: adm4->wilayah_id, kode_cuaca->cuaca_id, datetime->waktu_id."""
    wilayah = dict(
        con.execute("SELECT adm4, wilayah_id FROM dim_wilayah").fetchall()
    )
    cuaca = dict(
        con.execute("SELECT kode_cuaca, cuaca_id FROM dim_cuaca").fetchall()
    )
    waktu = {
        str(row[0]): row[1]
        for row in con.execute("SELECT datetime, waktu_id FROM dim_waktu").fetchall()
    }
    log.info(
        "lookups loaded — wilayah: %d, cuaca: %d, waktu: %d",
        len(wilayah), len(cuaca), len(waktu),
    )
    return wilayah, cuaca, waktu


def build_fact(
    silver: pd.DataFrame,
    wilayah_map: dict,
    cuaca_map: dict,
    waktu_map: dict,
) -> pd.DataFrame:
    rows = []
    skipped = 0
    for i, row in enumerate(silver.itertuples(index=False)):
        adm4       = str(getattr(row, COL_ADM4, None) or "")
        dt_raw     = getattr(row, COL_DATETIME, None)
        cuaca_raw  = getattr(row, COL_CUACA, None)
        kode_cuaca = str(int(cuaca_raw)) if cuaca_raw is not None and not pd.isna(cuaca_raw) else "-1"

        wilayah_id = wilayah_map.get(adm4)
        cuaca_id   = cuaca_map.get(kode_cuaca)
        dt_str     = "" if (dt_raw is None or pd.isnull(dt_raw)) else str(dt_raw)[:19]
        waktu_id   = waktu_map.get(dt_str)

        if wilayah_id is None or cuaca_id is None or waktu_id is None:
            skipped += 1
            continue

        rows.append({
            "fact_id":         i + 1,
            "wilayah_id":      wilayah_id,
            "cuaca_id":        cuaca_id,
            "waktu_id":        waktu_id,
            "suhu":            _float(getattr(row, COL_SUHU, None)),
            "kelembaban":      _float(getattr(row, COL_KELEMBABAN, None)),
            "kecepatan_angin": _float(getattr(row, COL_ANGIN_KEC, None)),
            "arah_angin":      str(getattr(row, COL_ANGIN_ARAH, "") or ""),
        })

    log.info("built fact_prakiraan_cuaca: %d rows  (skipped: %d)", len(rows), skipped)
    if skipped > 0:
        log.warning(
            "%d rows skipped — check that dim lookups cover all Silver BMKG values", skipped
        )
    return pd.DataFrame(rows)


def _float(val) -> float | None:
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None


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
    con.register("_fact_df", df)
    con.execute(
        "CREATE OR REPLACE TABLE fact_prakiraan_cuaca AS SELECT * FROM _fact_df"
    )
    n = con.execute("SELECT COUNT(*) FROM fact_prakiraan_cuaca").fetchone()[0]
    con.close()
    log.info("DuckDB table fact_prakiraan_cuaca: %d rows", n)


def run() -> None:
    silver = load_silver_bmkg()

    os.makedirs(os.path.dirname(config.DUCKDB_PATH), exist_ok=True)
    con = get_duckdb_connection()
    wilayah_map, cuaca_map, waktu_map = load_dim_lookups(con)
    con.close()

    df = build_fact(silver, wilayah_map, cuaca_map, waktu_map)
    write_delta(df)
    register_duckdb(df)
    log.info("fact_prakiraan done")


if __name__ == "__main__":
    run()
