-- Q1 (Aka): Rata-rata suhu maksimum per kabupaten untuk kondisi cuaca EKSTREM
-- Agregasi: AVG, MAX, MIN, COUNT  |  WHERE: kategori_risiko = 'Ekstrem'
-- Sumber: Gold Star Schema (fact_prakiraan_cuaca join dim_wilayah, dim_cuaca)
SELECT
    w.kabupaten,
    COUNT(*)                       AS jumlah_prakiraan,
    ROUND(AVG(f.suhu_max), 2)      AS rata_suhu_max,
    MAX(f.suhu_max)                AS suhu_max_tertinggi,
    MIN(f.suhu_min)                AS suhu_min_terendah,
    ROUND(AVG(f.kelembaban), 1)    AS rata_kelembaban
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
WHERE c.kategori_risiko = 'Ekstrem'
GROUP BY w.kabupaten
ORDER BY rata_suhu_max DESC;
