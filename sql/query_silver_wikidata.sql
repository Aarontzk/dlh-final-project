-- Q-Silver (Aka): Sebaran ADM4 (kelurahan+desa) per kecamatan di Jawa Timur
-- Runnable SEKARANG di Silver (tidak butuh Gold).
-- Agregasi: COUNT, AVG  |  WHERE: koordinat valid (lat/lon NOT NULL)
SELECT
    kecamatan,
    COUNT(*)                                 AS jumlah_adm4,
    SUM(CASE WHEN tipe = 'desa' THEN 1 END)       AS jml_desa,
    SUM(CASE WHEN tipe = 'kelurahan' THEN 1 END)  AS jml_kelurahan,
    ROUND(AVG(lat), 4)                       AS rata_lat,
    ROUND(AVG(lon), 4)                       AS rata_lon
FROM read_parquet('s3://silver/wikidata/parquet/jatim_adm4.parquet')
WHERE lat IS NOT NULL AND lon IS NOT NULL AND kecamatan IS NOT NULL
GROUP BY kecamatan
HAVING COUNT(*) >= 5
ORDER BY jumlah_adm4 DESC
LIMIT 20;
