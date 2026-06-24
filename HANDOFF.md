# HANDOFF - Wikidata ADM4 Jawa Timur (Aka)

Status per Wed 24 Jun: **Bronze + Silver Wikidata SELESAI**. Field schema final di bawah, dipakai Fabio (matching ADM) dan Farel (dim_wilayah Gold).

## Sumber
- Wikidata SPARQL, Provinsi Jawa Timur = `Q3586`
- ADM4 = kelurahan (`Q965568`) + desa (`Q26211545`), transitif via `P131*`
- 8557 ADM4 unik. Coord 8539 (99.8%). Populasi hanya 4 (Wikidata ID sparse - jangan andalkan populasi dari Wikidata).

## Lokasi data
- Bronze: `s3://bronze/wikidata/jatim_kelurahan_latest.json` (envelope + _metadata BX1)
- Silver Parquet: `s3://silver/wikidata/parquet/jatim_adm4.parquet`
- Silver Delta: `s3://silver/wikidata/delta/` (versioned, _delta_log)

## Silver schema (jatim_adm4) - FINAL, pakai ini

| kolom         | tipe     | catatan                                  |
|---------------|----------|------------------------------------------|
| wikidata_id   | string   | QID, contoh `Q11286977` (PK)             |
| nama_wilayah  | string   | nama desa/kelurahan (ADM4)               |
| tipe          | string   | `desa` atau `kelurahan`                   |
| parent_id     | string   | QID kecamatan (ADM3)                      |
| kecamatan     | string   | nama kecamatan (ADM3)                     |
| populasi      | Int64    | sering NULL (sparse)                      |
| area_km2      | float    | sering NULL                              |
| lat           | float    | ~99.8% terisi                            |
| lon           | float    | ~99.8% terisi                            |

## Untuk Farel (Gold dim_wilayah)
- dim_wilayah ADM4 ambil dari Silver Wikidata ini ATAU dari BMKG Fabio. Disarankan **BMKG sebagai sumber utama dim_wilayah** (kode ADM resmi + lengkap), Wikidata sebagai enrichment lat/lon kalau BMKG tidak punya.
- Matching antara Wikidata dan BMKG: by nama_wilayah + kecamatan (Wikidata tidak punya kode ADM4 resmi). Fuzzy match disarankan.
- Wikidata TIDAK punya kode adm4/adm3 numerik resmi -> kalau butuh kode, pakai punya BMKG.

## Untuk Fabio (BMKG)
- Tetap full ~7724 ADM4 Jatim. Share contoh JSON response BMKG ke Farel paling lambat malam ini buat finalisasi ERD.

## Cara baca dari DuckDB
```python
from setup_buckets import get_duckdb_connection
con = get_duckdb_connection()
con.execute("SELECT * FROM read_parquet('s3://silver/wikidata/parquet/jatim_adm4.parquet') LIMIT 5").fetchdf()
```
