-- Q5 (Farel): Total populasi terdampak cuaca EKSTREM per kabupaten
-- Agregasi: SUM, COUNT, AVG  |  WHERE: kategori_risiko = 'Ekstrem'
-- Sumber: Gold Star Schema (fact_prakiraan_cuaca join dim_wilayah, dim_cuaca)
SELECT
    w.kabupaten,
    SUM(DISTINCT w.populasi)              AS total_populasi_terdampak,
    COUNT(DISTINCT w.wilayah_id)          AS jumlah_wilayah_terdampak,
    COUNT(*)                              AS total_prakiraan_ekstrem,
    ROUND(AVG(f.suhu), 2)                 AS rata_suhu,
    ROUND(AVG(f.kelembaban), 1)           AS rata_kelembaban
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
WHERE c.kategori_risiko IN ('Tinggi', 'Ekstrem')
GROUP BY w.kabupaten
ORDER BY total_populasi_terdampak DESC;
