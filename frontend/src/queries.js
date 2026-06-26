// SQL builder untuk mode Jelajah + 6 preset pertanyaan.
// Semua nilai filter berasal dari dropdown/known-vocab, tapi tetap di-escape.

const sq = (v) => `'${String(v).replace(/'/g, "''")}'`;

// Kolom yang boleh jadi grouping (whitelist -> ekspresi SQL).
const GROUP_EXPR = {
  kabupaten: "w.kabupaten",
  kecamatan: "w.kecamatan",
  nama_desa: "w.nama_desa",
  deskripsi: "c.deskripsi",
  kategori_risiko: "c.kategori_risiko",
};

const BASE_JOINS = `
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id = w.wilayah_id
JOIN dim_cuaca   c ON f.cuaca_id   = c.cuaca_id
JOIN dim_waktu   t ON f.waktu_id   = t.waktu_id`;

/** Rakit klausa WHERE dari state filter. */
function whereClause(f) {
  const w = ["1=1"];
  if (f.kabupaten) w.push(`w.kabupaten = ${sq(f.kabupaten)}`);
  if (f.risiko?.length)
    w.push(`c.kategori_risiko IN (${f.risiko.map(sq).join(", ")})`);
  if (f.cuaca) w.push(`c.deskripsi = ${sq(f.cuaca)}`);
  if (f.suhuMin != null) w.push(`f.suhu >= ${Number(f.suhuMin)}`);
  if (f.suhuMax != null) w.push(`f.suhu <= ${Number(f.suhuMax)}`);
  if (f.tanggal) w.push(`t.tanggal = ${sq(f.tanggal)}`);
  return w.join("\n  AND ");
}

/** Query agregasi utama (tabel + chart). */
export function buildExploreSql(f) {
  const expr = GROUP_EXPR[f.groupBy] ?? "w.kabupaten";
  return `
SELECT
  ${expr}                                AS grup,
  COUNT(*)                               AS jumlah_prakiraan,
  COUNT(DISTINCT w.wilayah_id)           AS jumlah_wilayah,
  ROUND(AVG(f.suhu), 2)                  AS rata_suhu,
  ROUND(AVG(f.kelembaban), 1)            AS rata_kelembaban,
  ROUND(AVG(f.kecepatan_angin), 2)       AS rata_angin
${BASE_JOINS}
WHERE ${whereClause(f)}
GROUP BY ${expr}
ORDER BY jumlah_prakiraan DESC
LIMIT 100`;
}

/** Query ringkasan untuk kartu statistik. */
export function buildSummarySql(f) {
  return `
SELECT
  COUNT(*)                                              AS total_prakiraan,
  COUNT(DISTINCT w.wilayah_id)                          AS total_wilayah,
  ROUND(AVG(f.suhu), 1)                                 AS rata_suhu,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE c.kategori_risiko IN ('Tinggi','Ekstrem'))
    / NULLIF(COUNT(*), 0), 1)                           AS persen_risiko_tinggi
${BASE_JOINS}
WHERE ${whereClause(f)}`;
}

/** Query titik peta: 1 baris per wilayah + risiko tertinggi yang muncul. */
export function buildMapSql(f) {
  return `
WITH ranked AS (
  SELECT
    w.wilayah_id, w.nama_desa, w.kecamatan, w.kabupaten, w.lat, w.lon,
    CASE c.kategori_risiko
      WHEN 'Ekstrem' THEN 4 WHEN 'Tinggi' THEN 3
      WHEN 'Sedang' THEN 2 ELSE 1 END                   AS skor,
    c.kategori_risiko
  ${BASE_JOINS}
  WHERE ${whereClause(f)} AND w.lat IS NOT NULL
)
SELECT
  wilayah_id, nama_desa, kecamatan, kabupaten, lat, lon,
  COUNT(*)                                              AS jumlah_prakiraan,
  MAX(skor)                                             AS skor_maks,
  arg_max(kategori_risiko, skor)                        AS risiko_tertinggi
FROM ranked
GROUP BY wilayah_id, nama_desa, kecamatan, kabupaten, lat, lon
LIMIT 9000`;
}

// 6 preset pertanyaan (mirror sql/query_*.sql). Bisa langsung di-query().
export const PRESETS = [
  {
    id: "q1",
    judul: "Suhu rata-rata per kabupaten saat cuaca berisiko",
    desc: "Rata/maks/min suhu untuk kondisi risiko Tinggi & Ekstrem, per kabupaten.",
    sql: `
SELECT w.kabupaten,
  COUNT(*) AS jumlah_prakiraan,
  ROUND(AVG(f.suhu),2) AS rata_suhu,
  MAX(f.suhu) AS suhu_tertinggi,
  MIN(f.suhu) AS suhu_terendah,
  ROUND(AVG(f.kelembaban),1) AS rata_kelembaban
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id=w.wilayah_id
JOIN dim_cuaca c ON f.cuaca_id=c.cuaca_id
WHERE c.kategori_risiko IN ('Tinggi','Ekstrem')
GROUP BY w.kabupaten ORDER BY rata_suhu DESC`,
  },
  {
    id: "q2",
    judul: "Wilayah terdampak cuaca berbahaya per kecamatan",
    desc: "Jumlah desa/kelurahan terdampak risiko tinggi + rata kecepatan angin.",
    sql: `
SELECT w.kabupaten, w.kecamatan,
  COUNT(DISTINCT w.wilayah_id) AS jumlah_wilayah_terdampak,
  ROUND(AVG(f.kecepatan_angin),1) AS rata_kecepatan_angin,
  MAX(f.kecepatan_angin) AS angin_maks
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id=w.wilayah_id
JOIN dim_cuaca c ON f.cuaca_id=c.cuaca_id
WHERE c.kategori_risiko IN ('Tinggi','Ekstrem')
GROUP BY w.kabupaten, w.kecamatan
HAVING COUNT(DISTINCT w.wilayah_id) > 0
ORDER BY jumlah_wilayah_terdampak DESC LIMIT 50`,
  },
  {
    id: "q3",
    judul: "Distribusi kondisi cuaca per kabupaten",
    desc: "Frekuensi tiap kondisi cuaca + persentase dari total kabupaten.",
    sql: `
SELECT w.kabupaten, c.deskripsi AS kondisi_cuaca, c.kategori_risiko,
  COUNT(*) AS frekuensi,
  ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (PARTITION BY w.kabupaten),2) AS persen_dari_kabupaten
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id=w.wilayah_id
JOIN dim_cuaca c ON f.cuaca_id=c.cuaca_id
GROUP BY w.kabupaten, c.deskripsi, c.kategori_risiko
ORDER BY w.kabupaten, frekuensi DESC LIMIT 200`,
  },
  {
    id: "q4",
    judul: "Top 10 wilayah paling panas",
    desc: "Desa/kelurahan dengan rata-rata suhu tertinggi.",
    sql: `
SELECT w.nama_desa, w.kecamatan, w.kabupaten,
  COUNT(*) AS jumlah_prakiraan,
  ROUND(AVG(f.suhu),2) AS rata_suhu,
  MAX(f.suhu) AS suhu_maks, MIN(f.suhu) AS suhu_min,
  ROUND(AVG(f.kelembaban),1) AS rata_kelembaban
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id=w.wilayah_id
WHERE f.suhu IS NOT NULL
GROUP BY w.wilayah_id, w.nama_desa, w.kecamatan, w.kabupaten
ORDER BY rata_suhu DESC LIMIT 10`,
  },
  {
    id: "q5",
    judul: "Wilayah risiko tinggi/ekstrem per kabupaten",
    desc: "Jumlah wilayah & total prakiraan ekstrem per kabupaten.",
    sql: `
SELECT w.kabupaten,
  COUNT(DISTINCT w.wilayah_id) AS jumlah_wilayah_terdampak,
  COUNT(*) AS total_prakiraan_ekstrem,
  ROUND(AVG(f.suhu),2) AS rata_suhu,
  ROUND(AVG(f.kelembaban),1) AS rata_kelembaban
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id=w.wilayah_id
JOIN dim_cuaca c ON f.cuaca_id=c.cuaca_id
WHERE c.kategori_risiko IN ('Tinggi','Ekstrem')
GROUP BY w.kabupaten ORDER BY total_prakiraan_ekstrem DESC`,
  },
  {
    id: "q6",
    judul: "Ranking wilayah paling sering berisiko",
    desc: "Top 20 desa/kelurahan berdasarkan frekuensi cuaca risiko tinggi/ekstrem.",
    sql: `
SELECT w.kabupaten, w.kecamatan, w.nama_desa,
  COUNT(*) AS frekuensi_risiko,
  ROUND(AVG(f.suhu),2) AS rata_suhu,
  ROUND(AVG(f.kelembaban),1) AS rata_kelembaban,
  ROUND(AVG(f.kecepatan_angin),2) AS rata_angin_ms
FROM fact_prakiraan_cuaca f
JOIN dim_wilayah w ON f.wilayah_id=w.wilayah_id
JOIN dim_cuaca c ON f.cuaca_id=c.cuaca_id
WHERE c.kategori_risiko IN ('Tinggi','Ekstrem')
GROUP BY w.kabupaten, w.kecamatan, w.nama_desa
ORDER BY frekuensi_risiko DESC LIMIT 20`,
  },
];

// Vocab untuk isi filter (urut sesuai severity).
export const RISIKO_ORDER = ["Rendah", "Sedang", "Tinggi", "Ekstrem"];
// Selaras palet QuestUI: hijau quest-complete -> emas -> tembaga -> merah darah.
export const RISIKO_COLOR = {
  Rendah: "#22c55e",
  Sedang: "#ca8a04",
  Tinggi: "#c2410c",
  Ekstrem: "#991b1b",
};
