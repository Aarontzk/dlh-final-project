# PPT Outline - Data Lakehouse Prakiraan Cuaca Jawa Timur

Style: digital/minimalis. Audience: akademik. 12 slide.

## 1. Judul
Data Lakehouse Prakiraan Cuaca Jawa Timur
- Final Project Data Lakehouse
- Arsitektur Bronze - Silver - Gold
- Stack: MinIO + DuckDB + Delta Lake
- Tim: Aka, Fabio, Farel

## 2. Latar Belakang & Masalah
- Data cuaca & wilayah tersebar di banyak sumber (BMKG, Wikidata)
- Format mentah tidak siap analisis
- Butuh satu platform terpusat, murah, skalabel
- Solusi: arsitektur Data Lakehouse

## 3. Tujuan & Ruang Lingkup
- Bangun pipeline 3 layer (Bronze, Silver, Gold)
- Integrasi data BMKG + Wikidata wilayah Jawa Timur
- Sediakan query analitik prakiraan cuaca
- Cakupan: ~7724 ADM4 BMKG + 8557 ADM4 Wikidata

## 4. Arsitektur Lakehouse
- Bronze: data mentah apa adanya (JSON)
- Silver: bersih, terstruktur (Parquet + Delta)
- Gold: star schema siap analisis (Delta)
- Pemisahan compute (DuckDB) dan storage (MinIO)

## 5. Tech Stack
- MinIO: object storage S3-compatible (gudang data)
- DuckDB: engine query OLAP columnar (otak)
- Delta Lake: versioning & ACID di Silver/Gold
- Python: orkestrasi pipeline

## 6. Bronze Layer - Ingestion
- Wikidata via SPARQL (kelurahan+desa Jatim, Q3586)
- BMKG via REST API prakiraan cuaca
- Idempotency: MD5 checksum, skip jika data sama
- Simpan JSON raw ke bucket bronze

## 7. Silver Layer - Transformasi
- Parsing, dedup, type casting
- Output Parquet + Delta Lake
- Delta versioning (_delta_log)
- Tiap sumber dibersihkan terpisah

## 8. Gold Layer - Star Schema
- Fact: fact_prakiraan_cuaca (suhu, kelembaban, angin)
- Dimensi: dim_wilayah, dim_cuaca, dim_waktu
- Join antar sumber terjadi di sini
- Denormalized untuk query cepat

## 9. Analisis & Query
- Q1: rata-rata suhu per kabupaten saat cuaca ekstrem
- Q2: jumlah wilayah terdampak cuaca bahaya per kecamatan
- Dijalankan DuckDB langsung di atas data MinIO
- Setiap query: SUM/AVG/COUNT/MAX/MIN + WHERE

## 10. Bonus Tasks
- BX1: custom metadata di Bronze (timestamp, versi API, operator)
- BX2: perbandingan ukuran format (Parquet 39x lebih kecil dari JSON)
- BX3: EXPLAIN ANALYZE pada 2 query Gold

## 11. Demo & Hasil
- Bronze: 9910 row Wikidata, idempotent
- Silver: 8557 ADM4 unik, coord 99.8%
- Query end-to-end via DuckDB + MinIO
- Screenshot hasil query & MinIO console

## 12. Kesimpulan & Pembagian Tim
- Lakehouse berhasil integrasi multi-sumber
- Pemisahan storage/compute terbukti efisien
- Aka: Wikidata + bonus | Fabio: BMKG | Farel: Gold ETL
- Potensi lanjutan: tambah sumber & dashboard
