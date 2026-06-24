# BX3 - Query Explanation Analysis

## Tujuan

`EXPLAIN ANALYZE` menjalankan query sekaligus menampilkan execution plan aktual DuckDB. Bukti ini digunakan untuk menjelaskan:

- urutan scan, join, filter, agregasi, dan sorting;
- jumlah baris yang melewati setiap operator;
- waktu eksekusi aktual;
- filter pushdown dan projection pushdown pada operator scan.

BX3 merupakan komponen bonus **Query Explanation Analysis (+5%)**.

## Cara menjalankan

Jalankan dari root repository:

```powershell
py run_query.py sql/explain_query_5.sql
py run_query.py sql/explain_query_6.sql
```

Jalankan secara berurutan. DuckDB menggunakan satu file database lokal sehingga
dua proses query paralel dapat saling mengunci file.

## Hasil verifikasi lokal

Hasil verifikasi pada data saat ini:

| Query | Total time contoh | Baris setelah filter | Hasil agregasi |
|---|---:|---:|---:|
| Query 5 | 0,0123 detik | 578 | 18 kabupaten |
| Query 6 | 0,0177 detik | 578 | 475 wilayah, diambil Top 20 |

Waktu dapat sedikit berubah pada setiap komputer dan setiap eksekusi.

Execution plan memperlihatkan:

- `TABLE_SCAN fact_prakiraan_cuaca` hanya memproyeksikan kolom yang diperlukan.
- Dynamic filter membatasi rentang `cuaca_id` yang relevan pada fact scan.
- `TABLE_SCAN dim_cuaca` menampilkan filter kategori `Tinggi`/`Ekstrem`.
- Dua `HASH_JOIN` menghubungkan fact dengan `dim_cuaca` dan `dim_wilayah`.
- Query 5 memakai `HASH_GROUP_BY` lalu `ORDER_BY`.
- Query 6 memakai `HASH_GROUP_BY` lalu `TOP_N` sebanyak 20 baris.

## Operator yang perlu dijelaskan

### TABLE_SCAN

DuckDB membaca tabel yang diperlukan. Perhatikan bagian `Projections` dan `Filters`.

- `Projections` menunjukkan hanya kolom yang diperlukan query yang diteruskan dari scan. Ini merupakan bukti **projection pushdown**.
- `Filters` menunjukkan filter diterapkan sedekat mungkin dengan proses scan. Ini merupakan bukti **filter pushdown**.

### HASH_JOIN

DuckDB menggabungkan fact dengan dimension menggunakan key:

```text
fact.wilayah_id = dim_wilayah.wilayah_id
fact.cuaca_id   = dim_cuaca.cuaca_id
```

### FILTER

Operator ini mempertahankan kategori:

```text
Tinggi atau Ekstrem
```

Baris kategori Rendah dan Sedang tidak diteruskan ke agregasi.

### HASH_GROUP_BY

- Query 5 melakukan agregasi per kabupaten.
- Query 6 melakukan agregasi per kabupaten, kecamatan, dan desa.

### ORDER_BY / TOP_N

- Query 5 mengurutkan kabupaten berdasarkan populasi terdampak.
- Query 6 menggunakan `TOP_N` atau kombinasi order/limit untuk mengambil 20 wilayah dengan frekuensi risiko tertinggi.

## Screenshot yang harus diambil

Ambil screenshot terminal yang memperlihatkan:

1. Perintah yang dijalankan.
2. `Total Time`.
3. Operator `TABLE_SCAN` beserta `Projections`/`Filters`.
4. Operator `HASH_JOIN`.
5. Operator `HASH_GROUP_BY`.
6. `ORDER_BY` pada Query 5 atau `TOP_N` pada Query 6.

Jika seluruh plan terlalu panjang, gunakan dua screenshot per query: bagian atas untuk total time dan operator hasil, serta bagian bawah untuk scan/filter/projection.

## Narasi singkat untuk presentasi

> DuckDB terlebih dahulu membaca hanya kolom yang diperlukan dari fact dan dimension. Filter kategori risiko diterapkan sebelum agregasi sehingga baris berisiko rendah tidak diproses lebih lanjut. Setelah itu DuckDB menggunakan hash join untuk menghubungkan fact dengan dimension dan hash group by untuk menghitung agregasi. Query 6 memakai Top-N sehingga hanya 20 wilayah dengan frekuensi risiko tertinggi yang dikembalikan.
