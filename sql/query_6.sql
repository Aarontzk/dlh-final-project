-- Q6 (Farel): Ranking risiko wilayah berdasarkan frekuensi cuaca EKSTREM x kepadatan penduduk
-- Agregasi: COUNT, AVG, SUM  |  WHERE: kategori_risiko = 'Ekstrem', populasi & area valid
-- Sumber: Gold Star Schema (fact_prakiraan_cuaca join dim_wilayah, dim_cuaca)
--
-- skor_risiko = frekuensi_ekstrem * kepadatan_per_km2
-- Semakin tinggi skor, semakin padat penduduk di wilayah yang sering terkena cuaca ekstrem.
SELECT
    w.kabupaten,
    w.kecamatan,
    w.nama_desa,
    w.populasi,
    ROUND(w.area_km2, 2)                                              AS area_km2,
    ROUND(w.populasi / NULLIF(w.area_km2, 0), 2)                      AS kepadatan_per_km2,
    COUNT(*)                                                           AS frekuensi_ekstrem,
    ROUND(COUNT(*) * w.populasi / NULLIF(w.area_km2, 0), 2)           AS skor_risiko
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
WHERE c.kategori_risiko = 'Ekstrem'
  AND w.populasi  IS NOT NULL
  AND w.area_km2  IS NOT NULL
  AND w.area_km2  > 0
GROUP BY
    w.kabupaten, w.kecamatan, w.nama_desa, w.populasi, w.area_km2
ORDER BY skor_risiko DESC
LIMIT 20;
