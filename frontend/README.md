# Frontend: Eksplorasi Cuaca Jawa Timur

Web untuk menjelajah data Gold (prakiraan cuaca dan risiko bencana) tanpa menulis
SQL. DuckDB jalan langsung di browser lewat WASM. Kamu pilih filter, aplikasi yang
menyusun SQL-nya dan membaca langsung dari file Parquet.

## Stack

- Vite untuk build statik
- @duckdb/duckdb-wasm sebagai query engine di browser
- Chart.js untuk bar chart
- Leaflet untuk peta titik risiko (lat/lon dari `dim_wilayah`)

Tidak ada backend, dan tidak butuh MinIO menyala. Datanya empat file Parquet
(sekitar 750 KB) di `public/data/`, dibaca lewat HTTP range request.

## Fitur

| Mode | Isi |
|------|-----|
| Jelajah | Filter bebas (kabupaten, risiko, kondisi cuaca, rentang suhu, tanggal), hasilnya jadi kartu statistik, bar chart, dan tabel |
| Pertanyaan | 6 query siap pakai, sama dengan `sql/query_1..6.sql` |
| Peta | Titik desa/kelurahan, diwarnai per kategori risiko tertinggi |

## Jalanin lokal

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (base '/' otomatis saat dev)
```

## Refresh data

Kalau tabel Gold di DuckDB berubah, ekspor ulang Parquet dari root repo:

```bash
py export_parquet.py
```

## Deploy (GitHub Pages)

Workflow `.github/workflows/deploy-frontend.yml` build dan deploy otomatis tiap
push ke `main` yang menyentuh `frontend/`.

Sekali setup di repo: Settings → Pages → Source = GitHub Actions.

Live di `https://aarontzk.github.io/Data-Lakehouse-Prakiraan-Cuaca-Jawa-Timur/`
(base path sudah di-set `/Data-Lakehouse-Prakiraan-Cuaca-Jawa-Timur/` di
`vite.config.js`).
