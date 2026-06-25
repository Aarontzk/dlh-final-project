-- Q4 (Fabio): Top 10 wilayah dengan rata-rata suhu tertinggi
-- Agregasi: AVG, MAX, MIN, COUNT  |  WHERE: suhu IS NOT NULL
-- Sumber: fact_prakiraan_cuaca JOIN dim_wilayah
SELECT
    w.nama_desa,
    w.kecamatan,
    w.kabupaten,
    COUNT(*)                    AS jumlah_prakiraan,
    ROUND(AVG(f.suhu), 2)       AS rata_suhu,
    MAX(f.suhu)                 AS suhu_maks,
    MIN(f.suhu)                 AS suhu_min,
    ROUND(AVG(f.kelembaban), 1) AS rata_kelembaban
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
WHERE f.suhu IS NOT NULL
GROUP BY w.wilayah_id, w.nama_desa, w.kecamatan, w.kabupaten
ORDER BY rata_suhu DESC
LIMIT 10;
