-- BX3 (Farel): EXPLAIN ANALYZE Query 6
-- Menampilkan execution plan aktual, jumlah baris, dan waktu setiap operator.
EXPLAIN ANALYZE
SELECT
    w.kabupaten,
    w.kecamatan,
    w.nama_desa,
    w.provinsi,
    COUNT(*)                         AS frekuensi_risiko,
    ROUND(AVG(f.suhu), 2)            AS rata_suhu,
    ROUND(AVG(f.kelembaban), 1)      AS rata_kelembaban,
    ROUND(AVG(f.kecepatan_angin), 2) AS rata_angin_ms
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
WHERE c.kategori_risiko IN ('Tinggi', 'Ekstrem')
GROUP BY
    w.kabupaten,
    w.kecamatan,
    w.nama_desa,
    w.provinsi
ORDER BY frekuensi_risiko DESC
LIMIT 20;
