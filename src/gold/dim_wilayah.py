"""Gold layer: dim_wilayah — wilayah/kelurahan dimension (Star Schema).

Joins:
  - Silver BMKG Delta (primary)    : adm4, adm codes, kabupaten, provinsi, kecamatan, desa, lat, lon
  - Silver Wikidata Delta (enrich) : adm4 → populasi, area_km2

Writes to:
  - s3://gold/dim_wilayah/  (Delta Lake)
  - DuckDB table: dim_wilayah

Run: py -m src.gold.dim_wilayah
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

log = get_logger("gold_dim_wilayah")

SILVER_BMKG_DELTA_URI     = f"s3://{config.BUCKET_SILVER}/bmkg"
SILVER_WIKIDATA_DELTA_URI = f"s3://{config.BUCKET_SILVER}/wikidata"
DELTA_URI                 = f"s3://{config.BUCKET_GOLD}/dim_wilayah"

STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL":        f"http://{config.MINIO_ENDPOINT}",
    "AWS_ACCESS_KEY_ID":       config.MINIO_ACCESS_KEY,
    "AWS_SECRET_ACCESS_KEY":   config.MINIO_SECRET_KEY,
    "AWS_REGION":              "us-east-1",
    "AWS_ALLOW_HTTP":          "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}

_BMKG_COLS = ["adm4", "adm1", "adm2", "adm3", "provinsi", "kotkab", "kecamatan", "desa", "lat", "lon"]
_WIKI_COLS = ["adm4", "populasi", "area_km2"]


def load_bmkg_lokasi() -> pd.DataFrame:
    """One row per ADM4 — deduplicated from Silver BMKG forecast rows."""
    dt = DeltaTable(SILVER_BMKG_DELTA_URI, storage_options=STORAGE_OPTIONS)
    df = dt.to_pandas(columns=_BMKG_COLS)
    df = df[df["adm4"].notna() & (df["adm4"] != "")]
    df = df.drop_duplicates(subset=["adm4"], keep="first").reset_index(drop=True)
    log.info("Silver BMKG lokasi: %d unique adm4", len(df))
    return df


def load_wikidata_enrichment() -> pd.DataFrame:
    """populasi + area_km2 from Silver Wikidata, keyed by adm4."""
    dt = DeltaTable(SILVER_WIKIDATA_DELTA_URI, storage_options=STORAGE_OPTIONS)
    df = dt.to_pandas(columns=_WIKI_COLS)
    df = df[df["adm4"].notna()]
    df = df.sort_values("adm4").drop_duplicates(subset=["adm4"], keep="first")
    log.info("Silver Wikidata enrichment: %d rows with adm4", len(df))
    return df


def build_dim(bmkg: pd.DataFrame, wiki: pd.DataFrame) -> pd.DataFrame:
    df = bmkg.merge(wiki, on="adm4", how="left")

    df = df.rename(columns={
        "desa":   "nama_desa",
        "kotkab": "kabupaten",
    })

    df = df[[
        "adm4", "adm3", "adm2", "adm1",
        "nama_desa", "kecamatan", "kabupaten", "provinsi",
        "lat", "lon", "populasi", "area_km2",
    ]].copy()

    df.insert(0, "wilayah_id", range(1, len(df) + 1))
    df["wilayah_id"] = df["wilayah_id"].astype("int32")
    df["populasi"]   = pd.to_numeric(df["populasi"], errors="coerce").astype("Int64")
    df["area_km2"]   = pd.to_numeric(df["area_km2"], errors="coerce")
    df["lat"]        = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"]        = pd.to_numeric(df["lon"], errors="coerce")

    matched = int(df["populasi"].notna().sum())
    log.info(
        "dim_wilayah: %d rows | with_populasi=%d (%.1f%%) | with_coord=%d",
        len(df), matched, 100 * matched / len(df),
        int(df["lat"].notna().sum()),
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
    con.register("_dim_wilayah_df", df)
    con.execute("CREATE OR REPLACE TABLE dim_wilayah AS SELECT * FROM _dim_wilayah_df")
    n = con.execute("SELECT COUNT(*) FROM dim_wilayah").fetchone()[0]
    con.close()
    log.info("DuckDB table dim_wilayah: %d rows", n)


def run() -> None:
    bmkg = load_bmkg_lokasi()
    wiki = load_wikidata_enrichment()
    df   = build_dim(bmkg, wiki)
    write_delta(df)
    register_duckdb(df)
    log.info("dim_wilayah done")


if __name__ == "__main__":
    run()
