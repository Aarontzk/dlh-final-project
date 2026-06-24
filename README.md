# DLH Final Project - Data Lakehouse (MinIO + DuckDB)

Arsitektur Data Lakehouse 3 layer (Bronze -> Silver -> Gold) untuk data wilayah +
prakiraan cuaca Jawa Timur. Object storage: MinIO. Compute engine: DuckDB.

## Pembagian
- **Aka**: Wikidata SPARQL (ADM4 Jatim) - Bronze + Silver. Bonus BX1, BX2. Query Gold Q1, Q2.
- **Fabio**: BMKG prakiraan cuaca full Jatim (~7724 ADM4) - Bronze + Silver.
- **Farel**: Gold ETL (Star Schema) + bonus BX3.

## Stack
- MinIO `localhost:9000` (minioadmin/minioadmin), bucket: `bronze`, `silver`, `gold`
- DuckDB + httpfs (S3 path-style) ke MinIO
- Python: minio, duckdb, pandas, pyarrow, requests, deltalake

## Layer & format
| Layer  | Format                     | Isi                         |
|--------|----------------------------|-----------------------------|
| Bronze | JSON raw + metadata (BX1)  | response API/SPARQL apa adanya |
| Silver | Parquet + Delta Lake       | cleaned, deduped, typed, versioned |
| Gold   | Delta Lake Star Schema     | dim_* + fact_prakiraan_cuaca |

## Setup
```bash
py -m pip install -r requirements.txt
py setup_buckets.py
```

## Jalankan pipeline Aka (Wikidata)
```bash
py -m src.bronze.wikidata               # ingest -> bronze (idempotent, MD5)
py -m src.silver.wikidata               # bronze -> silver (parquet + delta)
py -m src.bronze.bx2_format_comparison  # BX2 size comparison
```

## Bonus tasks
- **BX1** (Aka): custom metadata di Bronze Wikidata - `ingestion_timestamp`, `source_api_version`, `operator_id`, `content_md5`, `row_count`. Lihat `_metadata` di bronze envelope.
- **BX2** (Aka): perbandingan ukuran format JSON vs Parquet vs Delta. Hasil: Parquet ~39x lebih kecil dari JSON.
- **BX3** (Farel): EXPLAIN ANALYZE pada 2 query Gold.

## Idempotency
Bronze pakai MD5 checksum payload. Re-run dengan data sama -> skip ingestion.

## Delta Lake versioning
Silver ditulis sebagai Delta table (`_delta_log`). Setiap overwrite menambah versi.

Lihat `HANDOFF.md` untuk schema field final.
