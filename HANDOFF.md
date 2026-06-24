# Handoff Dokumen — DLH Final Project
## Prakiraan Cuaca dan Mitigasi Bencana

**Kelompok:** MDM Company  
**Mata Kuliah:** Data Lakehouse (DLH) — Semester 4, ITS  
**Anggota:**

| NRP | Nama | Alias |
|---|---|---|
| 5026241130 | Muhammad Azka Bilfaqih | Aka |
| 5026241146 | Fabio Andrea Liui | Fabio |
| 5026241114 | Ahmad Maulana al Farel Rizantha | Farel |

**Deadline resmi:** Minggu, 28 Juni 2026 pukul 23:59 WIB  
**Target internal:** Sabtu, 27 Juni 2026 pukul 23:59 WIB

---

## Stack Teknologi

| Komponen | Tool |
|---|---|
| Object Storage | MinIO |
| Compute Engine | DuckDB |
| Pipeline Language | Python 3.x |
| Format Bronze | JSON (raw) |
| Format Silver | Parquet + Delta Lake (`_delta_log`) |
| Format Gold | Delta Lake, Star Schema |
| Query Interface | DBeaver / Python (duckdb) |

---

## Sumber Data

### 1. BMKG API (Primary — Fabio)
- **Endpoint:** `https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={kode_adm4}`
- **Cakupan:** Seluruh kelurahan Jawa Timur (prefix ADM4: `35.*.*.*`, ~7724 kelurahan)
- **Frekuensi:** per 3 jam, 7 hari ke depan
- **Format:** JSON nested — objek `lokasi` + array `data` forecast per timestamp
- **Sumber kode ADM4:** cahyadsn/wilayah (GitHub)

### 2. Wikidata SPARQL (Secondary — Aka)
- **Query URL:** https://w.wiki/R9Pb
- **Endpoint:** `https://query.wikidata.org/sparql`
- **Data yang diambil:** item, itemLabel, populasi (P1082), area (P2046), koordinat (P625 → lat/lon), parent wilayah (P131)
- **Format:** JSON
- **PENTING (untuk Farel):** Silver Wikidata SUDAH punya kolom `adm4` (kode BMKG resmi) hasil match ke master `Data ADM4/` — exact (nama_desa+kecamatan) + fallback koordinat terdekat. Match rate **8552/8557 (99.9%)**. Gold tinggal `JOIN ... ON wikidata.adm4 = bmkg.adm4`, tidak perlu fuzzy. Kolom Silver: wikidata_id, nama_wilayah, tipe, parent_id, kecamatan, populasi, area_km2, lat, lon, **adm4**, match_method.

### 3. cahyadsn/wilayah GitHub (Reference — Fabio)
- **URL:** https://github.com/cahyadsn/wilayah
- **Fungsi:** Sumber daftar kode ADM4 seluruh Indonesia untuk iterasi BMKG API
- **Filter yang dipakai:** prefix `35` untuk Jawa Timur

---

## Struktur Folder (Git Repo — Aka)

```
dlh-final-project/
├── src/
│   ├── bronze/
│   │   ├── bmkg.py            # Bronze BMKG ingestion
│   │   └── wikidata.py        # Bronze Wikidata ingestion
│   ├── silver/
│   │   ├── bmkg.py            # Silver BMKG cleaning
│   │   └── wikidata.py        # Silver Wikidata cleaning
│   └── gold/
│       ├── dim_cuaca.py       # dim_cuaca ETL (tidak butuh Silver)
│       ├── dim_waktu.py       # dim_waktu ETL (tidak butuh Silver)
│       ├── dim_wilayah.py     # dim_wilayah ETL (butuh Silver Wikidata + BMKG lokasi)
│       └── fact_prakiraan.py  # fact_prakiraan ETL (butuh semua dim)
├── sql/
│   ├── query_1.sql
│   ├── query_2.sql
│   ├── query_3.sql
│   ├── query_4.sql
│   ├── query_5.sql
│   └── query_6.sql
├── config.py                  # MinIO + DuckDB connection config
├── logger.py                  # Logging utility
├── requirements.txt
├── README.md
└── HANDOFF.md                 # dokumen ini
```

---

## Arsitektur MinIO Buckets

```
minio/
├── bronze/
│   ├── bmkg/
│   │   └── {adm4_code}/
│   │       └── raw_{timestamp}.json
│   ├── wikidata/
│   │   └── raw_{timestamp}.json
│   └── checksums/
│       └── checksums.json     # MD5 registry untuk idempotency
├── silver/
│   ├── bmkg/
│   │   ├── data.parquet
│   │   └── _delta_log/
│   └── wikidata/
│       ├── data.parquet
│       └── _delta_log/
└── gold/
    ├── dim_wilayah/
    ├── dim_cuaca/
    ├── dim_waktu/
    └── fact_prakiraan_cuaca/
```

---

## Gold Layer Schema (Star Schema)

### dim_wilayah
```sql
CREATE TABLE dim_wilayah (
    wilayah_id    INTEGER PRIMARY KEY,
    adm4          VARCHAR,
    adm3          VARCHAR,
    adm2          VARCHAR,
    adm1          VARCHAR,
    nama_desa     VARCHAR,
    kecamatan     VARCHAR,
    kabupaten     VARCHAR,
    provinsi      VARCHAR,
    lat           DOUBLE,
    lon           DOUBLE,
    populasi      BIGINT,
    area_km2      DOUBLE
);
```

### dim_cuaca
```sql
CREATE TABLE dim_cuaca (
    cuaca_id        INTEGER PRIMARY KEY,
    kode_cuaca      VARCHAR,
    deskripsi       VARCHAR,
    kategori_risiko VARCHAR    -- 'Rendah', 'Sedang', 'Tinggi', 'Ekstrem'
);
```

### dim_waktu
```sql
CREATE TABLE dim_waktu (
    waktu_id    INTEGER PRIMARY KEY,
    datetime    TIMESTAMP,
    tanggal     DATE,
    jam         INTEGER,
    hari        VARCHAR,
    bulan       INTEGER,
    tahun       INTEGER
);
```

### fact_prakiraan_cuaca
```sql
CREATE TABLE fact_prakiraan_cuaca (
    fact_id             INTEGER PRIMARY KEY,
    wilayah_id          INTEGER REFERENCES dim_wilayah(wilayah_id),
    cuaca_id            INTEGER REFERENCES dim_cuaca(cuaca_id),
    waktu_id            INTEGER REFERENCES dim_waktu(waktu_id),
    suhu_min            DOUBLE,
    suhu_max            DOUBLE,
    kelembaban          DOUBLE,
    kecepatan_angin     DOUBLE,
    arah_angin          VARCHAR
);
```

---

## Pembagian Tugas

### Prinsip rebalancing
Beban teknis berbanding terbalik dengan beban non-teknis. Fabio memegang pipeline teknis terberat (8000+ API call + nested JSON flatten), sehingga tidak dibebani bonus task dan PPT-nya minimal. Aka pipelinenya lebih ringan (1 SPARQL call), sehingga mengambil sebagian besar PPT, dua bonus task, dan seluruh produksi video.

---

### Aka — Muhammad Azka Bilfaqih (5026241130)

| Hari | Task |
|---|---|
| Tue 23 | Git repo structure + MinIO bucket setup (bronze/silver/gold) + DuckDB conn + config.py + logger.py |
| Wed 24 | Bronze: Wikidata SPARQL ingest + MD5 checksum idempotency |
| Wed 24 | BX1: tambah custom metadata (ingestion_timestamp, source_api_version, operator_id) |
| Wed 24 | PPT: latar belakang, problem statement, tujuan projek |
| Thu 25 | Silver: Wikidata clean — handle nulls, type enforce (pop→int, lat/lon→float), normalize strings, delta_log entries |
| Fri 26 | Draft Query 1 & 2 |
| Fri 26 | PPT: arsitektur diagram (Bronze→Silver→Gold bucket flow) + ERD Gold layer |
| Fri 26 | BX2: file format storage comparison — ukuran bytes JSON Bronze vs Parquet Silver vs Delta Gold (via boto3 / os.path.getsize) |
| Sat 27 | Run & finalize Query 1 & 2 |
| Sat 27 | PPT: MinIO bucket screenshots + query result screenshots + slide pembagian tugas |
| Sat 27 | Record own section + edit full video + upload YouTube Unlisted + submit Google Classroom |

**Bonus tasks:** BX1 (Wed 24), BX2 (Fri 26)  
**Query tanggung jawab:** Query 1 & 2

---

### Fabio — Fabio Andrea Liui (5026241146)

| Hari | Task |
|---|---|
| Tue 23 | BMKG API structure explore + download full ADM4 list Jawa Timur dari cahyadsn/wilayah (prefix '35', ~7724 kode) |
| Tue 23 | Rancang rate-limit strategy: delay antar request, retry logic, error handling per kode |
| Wed 24 | Bronze: iterate semua ADM4 Jatim → fetch JSON per kelurahan → store raw ke MinIO → MD5 per file, skip jika hash unchanged |
| Thu 25 | Silver: flatten nested JSON (lokasi obj + data array per timestamp) → tabular |
| Thu 25 | Handle anomalies & nulls, enforce types (temp→float, ts→datetime), write Parquet + delta_log versioning |
| Fri 26 | Draft Query 3 & 4 |
| Fri 26 | PPT: data spec — sumber data, contoh response JSON, data dictionary (field, tipe, jumlah baris per layer) |
| Sat 27 | Run & finalize Query 3 & 4 |
| Sat 27 | PPT: terminal ETL screenshots — log keberhasilan Bronze, Silver, Gold |
| Sat 27 | Record own section |

**Bonus tasks:** Tidak ada — dikompensasi beban teknis Bronze BMKG penuh.  
**Query tanggung jawab:** Query 3 & 4

**Catatan teknis Bronze BMKG:**
- Gunakan `time.sleep(0.1–0.3)` antar request untuk menghindari rate limit
- Simpan registry MD5 checksum ke `minio://bronze/checksums/checksums.json`
- Sebelum fetch, cek apakah hash file berubah. Jika sama, skip ingestion
- Jalankan script overnight dari Tue malam supaya Wed pagi sudah bisa fokus ke Silver logic

---

### Farel — Ahmad Maulana al Farel Rizantha (5026241114)

| Hari | Task |
|---|---|
| Tue 23 | Star Schema ERD draft (dim_wilayah, dim_cuaca, dim_waktu, fact_prakiraan) |
| Tue 23 | dim_cuaca: tulis manual dari dokumentasi BMKG — kode cuaca → deskripsi + kategori risiko (**tidak butuh Silver**) |
| Wed 24 | dim_waktu: generate dari forecast datetime range (interval 3 jam, 7 hari ke depan) (**tidak butuh Silver**) |
| Wed 24 | Refine ERD berdasarkan struktur Bronze output Aka dan Fabio + tulis Gold ETL function skeletons |
| Thu 25 | Finalize Gold CREATE TABLE definitions (DuckDB SQL) dari field Bronze yang sudah verified |
| Thu 25 | PPT: metodologi — diagram Medallion Architecture, idempotency mechanism, delta_log versioning, skema warehouse (ERD) |
| Thu 25 | PPT: sumber data — alamat API, screenshot response contoh, penjelasan fitur/variabel penting |
| Fri 26 | **CRITICAL PATH:** dim_wilayah (JOIN Wikidata Silver + BMKG lokasi) + fact_prakiraan_cuaca |
| Sat 27 | Run & finalize Query 5 & 6 |
| Sat 27 | BX3: EXPLAIN ANALYZE pada 2 query — screenshot output tree, highlight filter pushdown + projection pushdown |
| Sat 27 | Record own section |

**Bonus tasks:** BX3 (Sat 27)  
**Query tanggung jawab:** Query 5 & 6

**Catatan Gold ETL:**
- `dim_cuaca` dan `dim_waktu` TIDAK butuh Silver. Kerjakan Tue-Wed untuk kurangi bottleneck Fri.
- `dim_wilayah` butuh join: Wikidata Silver (item, itemLabel, pop, lat, lon) + BMKG Bronze lokasi field (adm4 sebagai join key)
- `fact_prakiraan_cuaca` butuh semua 3 dim selesai terlebih dahulu

---

## Critical Path & Dependencies

```
Tue 23    Aka: Bronze Wikidata ─────────────────────┐
          Fabio: Bronze BMKG (run overnight) ────────┤
                                                      ▼
Thu 25    Aka: Silver Wikidata ─────────────────────┐
          Fabio: Silver BMKG ───────────────────────┤ (kedua harus selesai Thu 25 malam)
                                                      ▼
Fri 26    Farel: dim_wilayah + fact_prakiraan ──────── GATE
                                                      ▼
Sat 27    Semua: Run 6 queries + video + submit
```

**Hard constraint:** Silver Aka dan Silver Fabio harus selesai dan dapat di-query paling lambat **Kamis 25 Juni malam**. Keterlambatan di sini langsung menunda Gold ETL dan semua queries.

---

## Query Analytics (6 total, 2 per orang)

Kriteria wajib per query: minimal 1 fungsi agregasi (SUM, AVG, COUNT, MAX, MIN) + klausa WHERE.

| Query | Owner | Topik |
|---|---|---|
| Q1 | Aka | Rata-rata suhu per kabupaten untuk kondisi cuaca kategori ekstrem |
| Q2 | Aka | Jumlah kelurahan dengan cuaca berbahaya per kecamatan |
| Q3 | Fabio | Distribusi frekuensi kondisi cuaca terbanyak per kabupaten WHERE populasi di atas threshold |
| Q4 | Fabio | Top 10 wilayah dengan rata-rata suhu maksimum tertinggi |
| Q5 | Farel | Total populasi yang terdampak cuaca ekstrem per kabupaten, diurutkan descending |
| Q6 | Farel | Ranking risiko wilayah berdasarkan frekuensi cuaca ekstrem dikalikan kepadatan penduduk |

---

## Bonus Points Checklist

| Bonus | Owner | Deskripsi | Target |
|---|---|---|---|
| BX1 Custom Metadata (+5%) | Aka | Kolom `ingestion_timestamp`, `source_api_version`, `operator_id` ditambahkan saat Bronze Wikidata | Wed 24 |
| BX2 File Format Comparison (+5%) | Aka | Tabel komparasi ukuran file (bytes): JSON Bronze vs Parquet Silver vs Delta Gold | Fri 26 |
| BX3 Query EXPLAIN ANALYZE (+5%) | Farel | Jalankan `EXPLAIN ANALYZE SELECT ...` di DuckDB pada 2 query, screenshot output tree, highlight filter/projection pushdown | Sat 27 |

---

## Struktur PPT

| Slide | Konten | Owner |
|---|---|---|
| 1 | Halaman judul + anggota tim | Aka |
| 2–4 | Latar belakang, problem statement, tujuan | Aka |
| 5–6 | Sumber data (alamat API, contoh response, fitur penting) | Farel |
| 7–9 | Metodologi: Medallion diagram, idempotency, delta_log, ERD Gold | Farel |
| 10–11 | Arsitektur diagram MinIO buckets + ERD Gold layer | Aka |
| 12–14 | Data spec + data dictionary (field, tipe, row count per layer) | Fabio |
| 15–19 | Hasil & dokumentasi: terminal ETL logs, MinIO bucket contents, 6 query results | Fabio + Aka |
| 20 | Slide pembagian tugas (siapa mengerjakan apa) | Aka |

---

## Checklist Video (10–20 menit)

- [ ] Aka: intro projek + Wikidata pipeline walkthrough + demo Query 1 & 2
- [ ] Fabio: BMKG pipeline walkthrough + delta_log demo + demo Query 3 & 4
- [ ] Farel: Gold ETL walkthrough + EXPLAIN ANALYZE + demo Query 5 & 6
- [ ] Aka: edit semua bagian menjadi 1 video utuh
- [ ] Upload ke YouTube dengan status akses **Unlisted**
- [ ] Cantumkan link YouTube di deskripsi pengumpulan Google Classroom

---

## Checklist Submission (cukup 1 orang — Aka)

- [ ] Source code repository (semua `.py` / `.ipynb`)
- [ ] Semua skrip SQL (6 file `.sql`)
- [ ] File PPT presentasi
- [ ] Link YouTube video (Unlisted, durasi 10–20 menit)

---

## Protokol Komunikasi

- Farel butuh info **struktur field Bronze** dari Aka (Wikidata) dan Fabio (BMKG) paling lambat **Wed 24 malam** untuk finalisasi Gold `CREATE TABLE` defs di Thu 25
- Silver Aka dan Silver Fabio harus done dan verified paling lambat **Thu 25 malam** agar Farel bisa eksekusi Gold ETL di Fri 26
- Jika ada blocking issue di tengah jalan, langsung kabari di grup. Jangan ditahan.
