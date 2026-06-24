# Status Pekerjaan Tim DLH Final Project

**Proyek:** Prakiraan Cuaca dan Mitigasi Bencana  
**Kelompok:** MDM Company  
**Tanggal pemeriksaan:** Rabu, 24 Juni 2026  
**Acuan:** `HANDOFF.md` dan artefak yang tersedia di repository `main`

> Dokumen ini membedakan antara **sudah tersedia dalam kode** dan **sudah terbukti berhasil dijalankan**. Status runtime tetap perlu dibuktikan melalui log terminal, isi bucket MinIO, row count, dan folder `_delta_log`.

## Ringkasan

Pekerjaan pipeline MinIO belum seluruhnya selesai. Implementasi Aka sudah cukup lengkap pada sisi kode Wikidata dan sudah memiliki enrichment ADM4. Fabio sudah menyelesaikan pengambilan data BMKG di luar repository; hasilnya tersedia sebagai `Data ADM4/`. Di dalam proyek, Fabio sudah memiliki Bronze uploader dan rancangan Silver BMKG, tetapi masih terdapat blocker path yang harus diselesaikan sebelum Farel dapat membangun Gold Layer.

### Critical path

```text
Aka: Silver Wikidata ──┐
                       ├──> Farel: dim_wilayah + fact_prakiraan ──> Query 1-6
Fabio: Silver BMKG ────┘
```

Silver Wikidata dan Silver BMKG harus selesai, dapat dibaca, dan memiliki kontrak kolom yang jelas paling lambat **Kamis, 25 Juni 2026 malam**.

---

## Status Aka - Wikidata

| Pekerjaan | Status | Bukti/Catatan |
|---|---|---|
| Struktur repository | Sudah tersedia | Folder `src/`, `sql/`, config, logger, dan setup bucket tersedia |
| Setup MinIO dan DuckDB | Sudah dikodekan | `setup_buckets.py` dan `config.py` tersedia |
| Bronze Wikidata SPARQL | Sudah dikodekan | `src/bronze/wikidata.py` |
| MD5 idempotency | Sudah dikodekan | Payload dibandingkan dengan `checksums/wikidata.md5` |
| BX1 custom metadata | Sudah dikodekan | `ingestion_timestamp`, `source_api_version`, `operator_id`, `content_md5`, dan `row_count` |
| Silver Wikidata cleaning | Sudah dikodekan | Null handling, casting numerik, dedup, dan normalisasi tersedia |
| Enrichment ADM4 | Sudah dikodekan | Exact match nama desa+kecamatan dengan fallback koordinat |
| Parquet dan Delta Lake | Sudah dikodekan | Output dirancang ke bucket `silver/wikidata` |
| BX2 format comparison | Sudah dikodekan | `src/bronze/bx2_format_comparison.py` |
| Query 1 dan Query 2 | Draft tersedia | `sql/query_1.sql` dan `sql/query_2.sql` |
| PPT | Baru berupa outline | Belum ditemukan file `.pptx` dan screenshot final |
| Demo Query 1-2 | Belum dapat dibuktikan | Menunggu Gold Layer selesai |
| Video dan submission | Belum | Dijadwalkan pada Sabtu, 27 Juni 2026 |

### Hal yang perlu diselesaikan Aka

- [ ] Jalankan Bronze Wikidata dan simpan log keberhasilan.
- [ ] Jalankan kembali Bronze untuk menunjukkan pesan `checksum unchanged` atau `skip`.
- [ ] Jalankan Silver Wikidata.
- [ ] Pastikan `silver/wikidata/data.parquet` tersedia.
- [ ] Pastikan `silver/wikidata/_delta_log/` tersedia.
- [ ] Catat row count, jumlah nilai populasi, dan jumlah koordinat yang terisi.
- [ ] Kirim atau upload seluruh output Silver Wikidata kepada Farel.
- [ ] Jalankan enrichment ADM4 dan catat persentase `exact`, `exact_coord`, `coord`, serta `unmatched`.
- [ ] Periksa sampel hasil mapping, terutama hasil dengan metode `coord`.
- [ ] Perbaiki filter Query 2 agar sesuai kategori risiko yang benar.
- [ ] Siapkan slide dan screenshot sesuai pembagian di `HANDOFF.md`.

### Validasi integrasi Wikidata

Silver Wikidata menghasilkan kolom dasar:

```text
wikidata_id
nama_wilayah
tipe
parent_id
kecamatan
populasi
area_km2
lat
lon
```

Kode saat ini sudah menambahkan `adm4` dan `match_method` menggunakan master lokasi BMKG. Sebelum output dianggap final, tim tetap harus memvalidasi:

1. Berapa persen baris yang berhasil memperoleh ADM4.
2. Berapa persen yang cocok secara exact dan berapa persen melalui koordinat.
3. Apakah hasil fallback koordinat benar pada sampel wilayah.
4. Apakah baris `unmatched` masih dapat digunakan atau harus dikeluarkan dari Gold.

### Catatan Query 2

Query 2 saat ini menggunakan:

```sql
WHERE c.kategori_risiko IN ('Ekstrem', 'Bahaya')
```

Sementara `dim_cuaca` menggunakan kategori:

```text
Rendah, Sedang, Tinggi, Ekstrem
```

Rekomendasi awal:

```sql
WHERE c.kategori_risiko IN ('Tinggi', 'Ekstrem')
```

---

## Status Fabio - BMKG

| Pekerjaan | Status | Bukti/Catatan |
|---|---|---|
| Data ADM4 Jawa Timur | Sudah tersedia | Terdapat 8.369 file JSON di `Data ADM4/` |
| Struktur data BMKG | Sudah dieksplorasi | JSON memuat lokasi dan forecast per timestamp |
| Bronze upload ke MinIO | Sudah dikodekan | `src/bronze/adm4.py` |
| MD5 idempotency | Sudah dikodekan | Registry `checksums/checksums.json` |
| Custom metadata BMKG | Sudah dikodekan | Timestamp, operator, ADM4, source file, dan MD5 |
| Fetch langsung dari API BMKG | Selesai di luar proyek | Hasil tersedia sebagai 8.369 file di `Data ADM4/` |
| Delay, retry, dan rate limiting API | Selesai di luar proyek | Dikonfirmasi oleh owner; bukan bagian audit pipeline MinIO ini |
| Silver flattening | Sudah dikodekan | `src/silver/bmkg.py` |
| Cleaning dan type enforcement | Sudah dikodekan | Casting timestamp/numerik, anomaly handling, dan dedup tersedia |
| Parquet dan Delta Lake | Sudah dikodekan | Belum terdapat bukti runtime terbaru |
| Query 3 dan Query 4 | Belum tersedia | `sql/query_3.sql` dan `sql/query_4.sql` belum ditemukan |
| Data dictionary dan PPT | Belum final | Belum ditemukan file PPT dan screenshot hasil |
| Video | Belum | Dijadwalkan pada Sabtu, 27 Juni 2026 |

### Perbaikan Silver BMKG

Bronze BMKG meng-upload object dengan pola:

```text
bmkg/{adm4_code}/raw_{timestamp}.json
```

Sebelumnya Silver BMKG masih mencari prefix lama:

```python
BRONZE_PREFIX = "adm4/raw/"
```

Prefix Silver sekarang sudah disesuaikan menjadi:

```python
BRONZE_PREFIX = "bmkg/"
```

Discovery object juga sudah diperbaiki agar:

- Hanya menerima pola `bmkg/{adm4_code}/raw_{timestamp}.json`.
- Mengabaikan `_manifest.json` dan path yang tidak valid.
- Memilih snapshot terbaru untuk setiap ADM4.
- Membatalkan penulisan Silver jika ada snapshot terbaru yang gagal diparse.

### Hal yang perlu diselesaikan Fabio

- [x] Perbaiki `BRONZE_PREFIX` pada `src/silver/bmkg.py` menjadi `bmkg/`.
- [x] Filter hanya raw snapshot dan pilih versi terbaru per ADM4.
- [ ] Jalankan Bronze BMKG dan simpan log jumlah uploaded/skipped/failed.
- [ ] Jalankan Bronze untuk kedua kali sebagai bukti idempotency.
- [ ] Jalankan Silver BMKG setelah prefix diperbaiki.
- [ ] Pastikan row count Silver lebih dari nol.
- [ ] Pastikan `silver/bmkg/data.parquet` tersedia.
- [ ] Pastikan `silver/bmkg/_delta_log/` tersedia.
- [ ] Kirim daftar nama kolom dan tipe data Silver BMKG kepada Farel.
- [ ] Buat `sql/query_3.sql` dan `sql/query_4.sql`.
- [ ] Siapkan data dictionary, row count per layer, dan screenshot terminal.

---

## Kontrak Data yang Dibutuhkan Farel

### Dari Silver Wikidata

Minimal diperlukan:

```text
nama_wilayah
kecamatan
populasi
area_km2
lat
lon
```

Tambahan yang sangat disarankan:

```text
adm4
kabupaten
provinsi
```

### Dari Silver BMKG

Minimal diperlukan:

```text
adm4
adm1
adm2
adm3
provinsi
kotkab
kecamatan
desa
lat
lon
datetime atau local_datetime
t
weather
hu
ws
wd
```

Farel tidak dapat memfinalisasi `dim_wilayah` dan `fact_prakiraan_cuaca` sebelum dua kontrak data tersebut disepakati.

---

## Bukti yang Harus Dikumpulkan

Setiap pipeline sebaiknya memiliki bukti berikut:

- [ ] Screenshot terminal run pertama Bronze.
- [ ] Screenshot terminal run kedua dengan status `skip`/checksum unchanged.
- [ ] Screenshot isi bucket Bronze.
- [ ] Screenshot terminal Silver dengan row count.
- [ ] Screenshot file Parquet di bucket Silver.
- [ ] Screenshot folder `_delta_log`.
- [ ] Catatan jumlah baris dan ukuran file per layer.
- [ ] Screenshot hasil query masing-masing anggota.

---

## Urutan Pengerjaan Mulai Sekarang

1. **Fabio:** perbaiki prefix Silver BMKG.
2. **Aka dan Fabio:** jalankan serta verifikasi Bronze dan Silver masing-masing.
3. **Aka dan Fabio:** kirim output Silver dan kontrak kolom kepada Farel.
4. **Tim:** validasi hasil mapping Wikidata ke ADM4 dan review baris unmatched.
5. **Farel:** bangun `dim_wilayah` dan `fact_prakiraan_cuaca`.
6. **Semua:** jalankan dan finalisasi Query 1-6.
7. **Semua:** lengkapi screenshot PPT dan rekaman video.

## Definisi Selesai

Pekerjaan Bronze/Silver dianggap selesai jika:

- Kode tersedia di repository.
- Pipeline berhasil dijalankan tanpa error.
- Data muncul di bucket MinIO dengan path yang disepakati.
- Run kedua membuktikan idempotency.
- Parquet dan Delta `_delta_log` tersedia.
- Row count serta data dictionary terdokumentasi.
- Output dapat dibaca oleh pipeline Gold milik Farel.
