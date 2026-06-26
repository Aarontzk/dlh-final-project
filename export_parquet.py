"""Export Gold-layer tables from DuckDB to Parquet for the static frontend.

The frontend (DuckDB-WASM) reads these Parquet files directly over HTTP, so
no MinIO/DuckDB server is needed at runtime. Run once whenever Gold data changes:

    py export_parquet.py
"""
import os

import duckdb

from config import DUCKDB_PATH

OUT_DIR = os.path.join("frontend", "public", "data")
TABLES = ["dim_wilayah", "dim_cuaca", "dim_waktu", "fact_prakiraan_cuaca"]


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    for table in TABLES:
        out = os.path.join(OUT_DIR, f"{table}.parquet").replace("\\", "/")
        con.execute(
            f"COPY (SELECT * FROM {table}) TO '{out}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        size_kb = os.path.getsize(out) / 1024
        print(f"  {table:24} {rows:>8} rows  ->  {out}  ({size_kb:.0f} KB)")
    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
