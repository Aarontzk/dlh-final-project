-- Q1 (Aka): Rata-rata suhu per kabupaten untuk kondisi cuaca berisiko TINGGI/EKSTREM
-- Agregasi: AVG, MAX, MIN, COUNT  |  WHERE: kategori_risiko IN ('Tinggi','Ekstrem')
-- Sumber: Gold Star Schema (fact_prakiraan_cuaca join dim_wilayah, dim_cuaca)
SELECT
    w.kabupaten,
    COUNT(*)                       AS jumlah_prakiraan,
    ROUND(AVG(f.suhu), 2)          AS rata_suhu,
    MAX(f.suhu)                     AS suhu_tertinggi,
    MIN(f.suhu)                     AS suhu_terendah,
    ROUND(AVG(f.kelembaban), 1)    AS rata_kelembaban
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
WHERE c.kategori_risiko IN ('Tinggi', 'Ekstrem')
GROUP BY w.kabupaten
ORDER BY rata_suhu DESC;
