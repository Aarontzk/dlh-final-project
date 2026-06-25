-- Q5 (Farel): Wilayah terdampak cuaca risiko tinggi/ekstrem per kabupaten
-- Agregasi: COUNT, AVG  |  WHERE: kategori_risiko IN ('Tinggi','Ekstrem')
-- Sumber: Gold Star Schema (fact_prakiraan_cuaca join dim_wilayah, dim_cuaca)
SELECT
    w.kabupaten,
    COUNT(DISTINCT w.wilayah_id)          AS jumlah_wilayah_terdampak,
    COUNT(*)                              AS total_prakiraan_ekstrem,
    ROUND(AVG(f.suhu), 2)                 AS rata_suhu,
    ROUND(AVG(f.kelembaban), 1)           AS rata_kelembaban
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
WHERE c.kategori_risiko IN ('Tinggi', 'Ekstrem')
GROUP BY w.kabupaten
ORDER BY total_prakiraan_ekstrem DESC;
