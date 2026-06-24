-- Gold Layer DDL — Star Schema (DuckDB)
-- Run sekali untuk membuat semua tabel di DuckDB, atau
-- biarkan masing-masing Gold ETL script yang membuatnya via
-- CREATE OR REPLACE TABLE ... AS SELECT.
--
-- Tabel:
--   dim_wilayah          — kelurahan/desa Jawa Timur (dibuat oleh dim_wilayah.py)
--   dim_cuaca            — kode cuaca BMKG + kategori risiko (dibuat oleh dim_cuaca.py)
--   dim_waktu            — datetime dimension 3-jam interval (dibuat oleh dim_waktu.py)
--   fact_prakiraan_cuaca — prakiraan cuaca per wilayah per waktu (dibuat oleh fact_prakiraan.py)

-- ============================================================
-- dim_wilayah
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_wilayah (
    wilayah_id  INTEGER PRIMARY KEY,
    adm4        VARCHAR,
    adm3        VARCHAR,
    adm2        VARCHAR,
    adm1        VARCHAR,
    nama_desa   VARCHAR,
    kecamatan   VARCHAR,
    kabupaten   VARCHAR,
    provinsi    VARCHAR,
    lat         DOUBLE,
    lon         DOUBLE,
    populasi    BIGINT,
    area_km2    DOUBLE
);

-- ============================================================
-- dim_cuaca
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_cuaca (
    cuaca_id        INTEGER PRIMARY KEY,
    kode_cuaca      VARCHAR,   -- kode numerik BMKG sebagai string ('0','60','95', ...)
    deskripsi       VARCHAR,   -- label cuaca bahasa Indonesia
    kategori_risiko VARCHAR    -- 'Rendah' | 'Sedang' | 'Tinggi' | 'Ekstrem'
);

-- ============================================================
-- dim_waktu
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_waktu (
    waktu_id  INTEGER PRIMARY KEY,
    datetime  TIMESTAMP,
    tanggal   VARCHAR,   -- 'YYYY-MM-DD'
    jam       INTEGER,   -- 0, 3, 6, 9, 12, 15, 18, 21
    hari      VARCHAR,   -- 'Senin' ... 'Minggu'
    bulan     INTEGER,
    tahun     INTEGER
);

-- ============================================================
-- fact_prakiraan_cuaca
-- ============================================================
CREATE TABLE IF NOT EXISTS fact_prakiraan_cuaca (
    fact_id         INTEGER PRIMARY KEY,
    wilayah_id      INTEGER REFERENCES dim_wilayah(wilayah_id),
    cuaca_id        INTEGER REFERENCES dim_cuaca(cuaca_id),
    waktu_id        INTEGER REFERENCES dim_waktu(waktu_id),
    suhu            DOUBLE,    -- suhu prakiraan per slot (°C)
    kelembaban      DOUBLE,
    kecepatan_angin DOUBLE,
    arah_angin      VARCHAR
);
