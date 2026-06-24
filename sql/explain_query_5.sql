-- BX3 (Farel): EXPLAIN ANALYZE Query 5
-- Menampilkan execution plan aktual, jumlah baris, dan waktu setiap operator.
EXPLAIN ANALYZE
SELECT
    w.kabupaten,
    SUM(DISTINCT w.populasi)               AS total_populasi_terdampak,
    COUNT(DISTINCT w.wilayah_id)           AS jumlah_wilayah_terdampak,
    COUNT(*)                               AS total_prakiraan_ekstrem,
    ROUND(AVG(f.suhu), 2)                  AS rata_suhu,
    ROUND(AVG(f.kelembaban), 1)            AS rata_kelembaban
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
WHERE c.kategori_risiko IN ('Tinggi', 'Ekstrem')
GROUP BY w.kabupaten
ORDER BY total_populasi_terdampak DESC;
