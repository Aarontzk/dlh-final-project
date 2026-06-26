<div align="center">

# 🌦️ Data Lakehouse Prakiraan Cuaca Jawa Timur

**Integrasi data BMKG & Wikidata untuk analisis risiko bencana hidrometeorologi**

Final Project — *Data Lakehouse (DLH)* · Semester 4 · Institut Teknologi Sepuluh Nopember

![Storage](https://img.shields.io/badge/storage-MinIO-C72E49)
![Compute](https://img.shields.io/badge/compute-DuckDB-FFF000)
![Table](https://img.shields.io/badge/table_format-Delta_Lake-00ADD8)
![Arch](https://img.shields.io/badge/architecture-Medallion-1E90FF)
![Python](https://img.shields.io/badge/python-3.x-3776AB)

</div>

---

## 🎯 Masalah yang diselesaikan

Setiap tahun Indonesia mengalami **2.000+ bencana hidrometeorologi** — banyak dipicu cuaca ekstrem yang sebetulnya bisa diprediksi. BMKG merilis prakiraan tiap kelurahan **setiap 3 jam**, tapi datanya tersebar dalam ribuan JSON nested dan terpisah dari profil wilayah (populasi, luas, koordinat).

> **Pertanyaan kunci:** bagaimana menyatukan data cuaca (BMKG) dan profil wilayah (Wikidata) Jawa Timur dalam satu platform yang murah, skalabel, dan siap dianalisis?

**Jawabannya:** sebuah **Data Lakehouse** 3 lapis — object storage murah (MinIO) dipisah dari compute (DuckDB), dengan tabel ber-versi (Delta Lake) dan pipeline yang idempoten.

---

## 🏛️ Arsitektur — Medallion

```
   SUMBER                BRONZE                 SILVER                  GOLD
 ─────────          (raw, apa adanya)     (bersih, typed, ver)    (siap analisis)
                                                                
  Wikidata  ─SPARQL─►  bronze/wikidata ──►  silver/wikidata  ──┐
  (populasi,           + _metadata (BX1)     parquet + delta    │   ┌──────────────┐
   area, koord)        MD5 idempotency       + enrich adm4      ├──►│  STAR SCHEMA │
                                                                │   │ dim_wilayah  │
  BMKG API  ─8369 ─►  bronze/bmkg/{adm4} ─►  silver/bmkg    ────┘   │ dim_cuaca    │──► 6 Query
  (prakiraan          + _metadata (BX1)      parquet + delta        │ dim_waktu    │    Analitik
   per 3 jam)         MD5 idempotency        flatten + clean        │ fact_*       │
                                                                    └──────────────┘
        ╰─────────────── MinIO (object storage) ───────────────╯   ╰─ DuckDB (compute) ─╯
```

| Layer | Format | Isi |
|-------|--------|-----|
| 🥉 **Bronze** | JSON mentah + envelope `_metadata` | response API/SPARQL apa adanya, idempoten via MD5 |
| 🥈 **Silver** | Parquet + **Delta Lake** (`_delta_log`) | cleaned, deduped, typed, ber-versi |
| 🥇 **Gold** | **Delta Lake** Star Schema + tabel DuckDB | `dim_*` + `fact_prakiraan_cuaca`, siap di-query |

---

## 🧰 Stack

| Komponen | Tool | Catatan |
|---|---|---|
| Object Storage | **MinIO** | `localhost:9000`, bucket `bronze` / `silver` / `gold` |
| Compute Engine | **DuckDB** | + `httpfs`, baca Delta/Parquet langsung dari MinIO (S3 path-style) |
| Table Format | **Delta Lake** | versioning ACID via `_delta_log` |
| Bahasa | **Python 3.x** | `minio`, `duckdb`, `pandas`, `pyarrow`, `requests`, `deltalake` |

---

## 🚀 Quick Start

**Prasyarat:** MinIO sudah jalan di `127.0.0.1:9000` (default kredensial `minioadmin` / `minioadmin`).

```bash
# 1. Install dependency
py -m pip install -r requirements.txt

# 2. Buat bucket + cek koneksi DuckDB
py setup_buckets.py
```

Override kredensial/endpoint lewat env var bila perlu: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_SECURE`.

### Jalankan pipeline (urut)

```bash
# ── BRONZE ───────────────────────────────────────────────
py -m src.bronze.wikidata     # SPARQL Wikidata  -> bronze/wikidata
py -m src.bronze.adm4         # 8369 JSON lokal  -> bronze/bmkg/{adm4}

# ── SILVER ───────────────────────────────────────────────
py -m src.silver.wikidata     # clean + enrich adm4 -> silver/wikidata (parquet + delta)
py -m src.silver.bmkg         # flatten + clean     -> silver/bmkg (parquet + delta)

# ── GOLD (star schema) ───────────────────────────────────
py -m src.gold.dim_cuaca      # statis, tak butuh Silver
py -m src.gold.dim_waktu      # butuh Silver BMKG
py -m src.gold.dim_wilayah    # butuh Silver BMKG + Wikidata
py -m src.gold.fact_prakiraan # butuh semua dim + Silver BMKG

# ── QUERY ────────────────────────────────────────────────
py run_query.py sql/query_1.sql   # ganti 1..6
```

> 💡 Tiap script juga bisa dijalankan langsung lewat tombol **Run** VS Code (ada bootstrap `sys.path`), tak harus pakai `-m`.

---

## 🗂️ Sumber Data

| # | Sumber | Owner | Detail |
|---|--------|-------|--------|
| 1 | **BMKG API** *(primary)* | Fabio | `api.bmkg.go.id/publik/prakiraan-cuaca?adm4={kode}` — seluruh kelurahan Jatim (prefix ADM4 `35.*`, ~7.724 wilayah), per 3 jam, 7 hari ke depan. JSON nested (`lokasi` + array `data`). Hasil fetch tersimpan sebagai **8369 file** di `Data ADM4/`. |
| 2 | **Wikidata SPARQL** *(secondary)* | Azka | `query.wikidata.org/sparql` — kelurahan (Q965568) + desa (Q26211545) di Jawa Timur (Q3586), transitif via `P131*`. Ambil populasi (P1082), area (P2046), koordinat (P625), parent (P131). |
| 3 | **cahyadsn/wilayah** *(reference)* | Fabio | Sumber daftar kode ADM4 Indonesia, difilter prefix `35` untuk iterasi BMKG API. |

🔗 **Join key:** Silver Wikidata di-*enrich* dengan kolom `adm4` (kode BMKG resmi) — exact match `nama_desa + kecamatan`, fallback koordinat terdekat (~5 km). Match rate **~99,9%**, jadi Gold tinggal `JOIN ON adm4` tanpa fuzzy.

---

## 🏗️ Layout Bucket MinIO

```
bronze/
├── wikidata/
│   ├── latest.json                 # pointer snapshot terbaru
│   └── raw_{ts}.json               # snapshot ber-timestamp
├── bmkg/
│   ├── {adm4}/raw_{ts}.json        # 1 objek per kelurahan per run
│   └── _manifest.json              # ringkasan run (uploaded/skipped/failed)
└── checksums/checksums.json        # registry MD5 gabungan (idempotency)

silver/
├── wikidata/  ├── data.parquet  └── _delta_log/
└── bmkg/      ├── data.parquet  └── _delta_log/

gold/
├── dim_wilayah/   ├── dim_cuaca/
├── dim_waktu/     └── fact_prakiraan_cuaca/      # semua Delta Lake
```

---

## ⭐ Gold — Star Schema

```
                  ┌─────────────┐
                  │  dim_waktu  │
                  └──────┬──────┘
                         │ waktu_id
   ┌─────────────┐  ┌────┴───────────────────┐  ┌─────────────┐
   │ dim_wilayah ├──┤  fact_prakiraan_cuaca  ├──┤  dim_cuaca  │
   └─────────────┘  └────────────────────────┘  └─────────────┘
      wilayah_id      suhu · kelembaban           cuaca_id
                      kecepatan_angin · arah_angin
```

| Tabel | Kolom utama | Grain / sumber |
|-------|-------------|----------------|
| `fact_prakiraan_cuaca` | `fact_id`, `wilayah_id`, `cuaca_id`, `waktu_id`, `suhu`, `kelembaban`, `kecepatan_angin`, `arah_angin` | 1 baris per (wilayah × waktu) prakiraan |
| `dim_wilayah` | `wilayah_id`, `adm1..adm4`, `nama_desa`, `kecamatan`, `kabupaten`, `provinsi`, `lat`, `lon`, `populasi`, `area_km2` | Silver BMKG lokasi + enrich Wikidata |
| `dim_cuaca` | `cuaca_id`, `kode_cuaca`, `deskripsi`, `kategori_risiko` | 14 kode BMKG → risiko Rendah/Sedang/Tinggi/Ekstrem (statis) |
| `dim_waktu` | `waktu_id`, `datetime`, `tanggal`, `jam`, `hari`, `bulan`, `tahun` | unique slot dari Silver BMKG |

DDL lengkap: [`sql/schema_gold.sql`](sql/schema_gold.sql).

---

## 📊 Query Analitik (6)

Tiap query wajib ≥1 fungsi agregasi (`SUM`/`AVG`/`COUNT`/`MAX`/`MIN`) + klausa `WHERE`.

| Query | Owner | Topik |
|-------|-------|-------|
| [Q1](sql/query_1.sql) | Azka | Rata-rata suhu per kabupaten saat cuaca berisiko Tinggi/Ekstrem |
| [Q2](sql/query_2.sql) | Azka | Jumlah kelurahan/desa terdampak cuaca berbahaya per kecamatan |
| [Q3](sql/query_3.sql) | Fabio | Distribusi frekuensi kondisi cuaca terbanyak per kabupaten (WHERE populasi > 0) |
| [Q4](sql/query_4.sql) | Fabio | Top 10 wilayah dengan rata-rata suhu tertinggi |
| [Q5](sql/query_5.sql) | Farel | Wilayah terdampak cuaca risiko tinggi/ekstrem per kabupaten |
| [Q6](sql/query_6.sql) | Farel | Ranking wilayah berdasar frekuensi cuaca risiko tinggi/ekstrem |

---

## 🎁 Bonus Tasks

| Bonus | Owner | Deskripsi |
|-------|-------|-----------|
| **BX1** Custom Metadata *(+5%)* | Azka | Envelope `_metadata` di Bronze: `ingestion_timestamp`, `source_api_version`, `operator_id`, `content_md5`, `row_count`. Lihat `_metadata` di tiap objek Bronze. |
| **BX2** File Format Comparison *(+5%)* | Azka | Bandingkan ukuran JSON vs Parquet vs Delta. Jalankan `py -m src.bronze.bx2_format_comparison`. Hasil: Parquet jauh lebih kecil dari JSON. |
| **BX3** Query EXPLAIN ANALYZE *(+5%)* | Farel | `EXPLAIN ANALYZE` 2 query Gold — bukti *filter & projection pushdown*. Jalankan `py run_query.py sql/explain_query_5.sql` & `sql/explain_query_6.sql`. |

---

## 🔁 Konsep kunci

**Idempotency (Bronze)** — payload di-hash MD5 dan dicek ke `checksums/checksums.json`. Hash sama → ingestion di-*skip*. Re-run aman, tanpa duplikat.

**Versioning (Silver & Gold)** — tiap tabel ditulis sebagai Delta Lake. Tiap `overwrite` menambah versi baru di `_delta_log` → riwayat + jaminan ACID.

**Separation of concerns** — storage (MinIO) terpisah dari compute (DuckDB). Bisa scale & ganti engine tanpa pindah data.

---

## 📁 Struktur Repo

```
.
├── src/
│   ├── bronze/
│   │   ├── wikidata.py              # Bronze: SPARQL Wikidata (+ BX1 metadata)
│   │   ├── adm4.py                  # Bronze: upload 8369 JSON lokal -> MinIO
│   │   └── bx2_format_comparison.py # BX2: komparasi ukuran format
│   ├── silver/
│   │   ├── wikidata.py              # Silver: clean + enrich adm4
│   │   └── bmkg.py                  # Silver: flatten + clean forecast
│   └── gold/
│       ├── dim_cuaca.py  dim_waktu.py  dim_wilayah.py
│       └── fact_prakiraan.py
├── sql/
│   ├── query_1.sql … query_6.sql    # 6 query analitik
│   ├── explain_query_5.sql  explain_query_6.sql   # BX3
│   └── schema_gold.sql              # DDL star schema
├── Data ADM4/                       # 8369 JSON BMKG mentah (sumber Bronze BMKG)
├── config.py                        # konfigurasi MinIO + DuckDB + Wikidata + BX1
├── logger.py                        # logger console + rotating file
├── setup_buckets.py                 # buat bucket + helper koneksi DuckDB/MinIO
├── run_query.py                     # eksekusi file .sql terhadap DuckDB
├── requirements.txt
├── HANDOFF.md                       # dokumen serah-terima teknis tim
└── README.md
```

---

## 👥 Tim — *MDM Company*

| NRP | Nama | Alias | Tanggung jawab |
|-----|------|-------|----------------|
| 5026241130 | Muhammad Azka Bilfaqih | **Azka** | Wikidata (Bronze + Silver), Q1–Q2, BX1, BX2 |
| 5026241146 | Fabio Andrea Liui | **Fabio** | BMKG ~7.724 ADM4 (Bronze + Silver), Q3–Q4 |
| 5026241114 | Ahmad Maulana al Farel Rizantha | **Farel** | Gold Star Schema (dim + fact), Q5–Q6, BX3 |

📄 Detail teknis & kontrak data antar-layer: lihat [`HANDOFF.md`](HANDOFF.md).
