-- Q2 (Aka): Jumlah kelurahan/desa terdampak cuaca BERBAHAYA per kecamatan
-- Agregasi: COUNT (distinct wilayah), AVG  |  WHERE: kategori_risiko berbahaya
-- Sumber: Gold Star Schema (fact_prakiraan_cuaca join dim_wilayah, dim_cuaca, dim_waktu)
SELECT
    w.kabupaten,
    w.kecamatan,
    COUNT(DISTINCT w.wilayah_id)        AS jumlah_wilayah_terdampak,
    ROUND(AVG(f.kecepatan_angin), 1)    AS rata_kecepatan_angin,
    MAX(f.kecepatan_angin)              AS angin_maks
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
WHERE c.kategori_risiko IN ('Ekstrem', 'Bahaya')
GROUP BY w.kabupaten, w.kecamatan
HAVING COUNT(DISTINCT w.wilayah_id) > 0
ORDER BY jumlah_wilayah_terdampak DESC;
