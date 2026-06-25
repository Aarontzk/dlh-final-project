-- Q3 (Fabio): Distribusi frekuensi kondisi cuaca terbanyak per kabupaten
-- WHERE populasi wilayah > 0 (threshold: hanya wilayah yang punya data populasi)
-- Agregasi: COUNT, SUM window untuk persentase
-- Sumber: fact_prakiraan_cuaca JOIN dim_wilayah, dim_cuaca
SELECT
    w.kabupaten,
    c.deskripsi                                                         AS kondisi_cuaca,
    c.kategori_risiko,
    COUNT(*)                                                            AS frekuensi,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY w.kabupaten),
        2
    )                                                                   AS persen_dari_kabupaten
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
WHERE w.populasi IS NOT NULL
  AND w.populasi > 0
GROUP BY w.kabupaten, c.deskripsi, c.kategori_risiko
ORDER BY w.kabupaten, frekuensi DESC;
