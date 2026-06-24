-- Q6 (Farel): Ranking wilayah berdasarkan frekuensi cuaca risiko tinggi/ekstrem
-- Agregasi: COUNT, AVG  |  WHERE: kategori_risiko IN ('Tinggi','Ekstrem')
-- Sumber: Gold Star Schema (fact_prakiraan_cuaca join dim_wilayah, dim_cuaca)
--
-- Catatan: data populasi dari Wikidata sangat terbatas untuk kelurahan Jawa Timur,
-- sehingga ranking menggunakan frekuensi kejadian cuaca berisiko sebagai skor utama.
SELECT
    w.kabupaten,
    w.kecamatan,
    w.nama_desa,
    w.provinsi,
    COUNT(*)                        AS frekuensi_risiko,
    ROUND(AVG(f.suhu), 2)           AS rata_suhu,
    ROUND(AVG(f.kelembaban), 1)     AS rata_kelembaban,
    ROUND(AVG(f.kecepatan_angin), 2) AS rata_angin_ms
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
WHERE c.kategori_risiko IN ('Tinggi', 'Ekstrem')
GROUP BY
    w.kabupaten, w.kecamatan, w.nama_desa, w.provinsi
ORDER BY frekuensi_risiko DESC
LIMIT 20;
