// DuckDB-WASM bootstrap: jalankan mesin DuckDB di dalam browser (Web Worker),
// muat 4 Parquet Gold dari /public/data, lalu bikin VIEW dengan nama tabel asli
// supaya semua SQL Gold (sql/query_*.sql) bisa dipakai apa adanya.
import * as duckdb from "@duckdb/duckdb-wasm";

const TABLES = ["dim_wilayah", "dim_cuaca", "dim_waktu", "fact_prakiraan_cuaca"];

let _conn = null;

// URL Parquet relatif terhadap base path (penting untuk GitHub Pages subpath).
function dataUrl(name) {
  return new URL(`data/${name}.parquet`, document.baseURI).href;
}

async function bootWorker() {
  // Ambil bundle WASM dari jsDelivr; tak perlu bundling lokal, aman utk static host.
  const bundles = duckdb.getJsDelivrBundles();
  const bundle = await duckdb.selectBundle(bundles);

  const workerUrl = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker}");`], {
      type: "text/javascript",
    }),
  );
  const worker = new Worker(workerUrl);
  const logger = new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING);
  const db = new duckdb.AsyncDuckDB(logger, worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  URL.revokeObjectURL(workerUrl);
  return db;
}

/**
 * Inisialisasi DB + registrasi Parquet sebagai VIEW. Idempotent.
 * @param {(msg: string) => void} onProgress
 * @returns {Promise<import("@duckdb/duckdb-wasm").AsyncDuckDBConnection>}
 */
export async function initDb(onProgress = () => {}) {
  if (_conn) return _conn;

  onProgress("menyalakan DuckDB-WASM…");
  const db = await bootWorker();
  const conn = await db.connect();

  for (const t of TABLES) {
    onProgress(`memuat ${t}…`);
    await db.registerFileURL(
      `${t}.parquet`,
      dataUrl(t),
      duckdb.DuckDBDataProtocol.HTTP,
      false,
    );
    await conn.query(
      `CREATE OR REPLACE VIEW ${t} AS SELECT * FROM read_parquet('${t}.parquet')`,
    );
  }

  _conn = conn;
  return conn;
}

/**
 * Jalankan SQL, kembalikan array of plain objects.
 * @param {string} sql
 * @returns {Promise<Record<string, unknown>[]>}
 */
export async function query(sql) {
  if (!_conn) throw new Error("DB belum di-init. Panggil initDb() dulu.");
  const result = await _conn.query(sql);
  // Arrow Table -> array objek biasa; konversi BigInt -> Number agar aman di UI.
  return result.toArray().map((row) => {
    const obj = row.toJSON();
    for (const k of Object.keys(obj)) {
      if (typeof obj[k] === "bigint") obj[k] = Number(obj[k]);
    }
    return obj;
  });
}
