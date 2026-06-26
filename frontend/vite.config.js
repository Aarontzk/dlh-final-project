import { defineConfig } from "vite";

// Repo di-deploy ke GitHub Pages project site:
//   https://aarontzk.github.io/Data-Lakehouse-Prakiraan-Cuaca-Jawa-Timur/
// Jadi base harus path nama repo. Override via env VITE_BASE saat lokal.
export default defineConfig({
  base: process.env.VITE_BASE ?? "/Data-Lakehouse-Prakiraan-Cuaca-Jawa-Timur/",
  build: {
    target: "esnext", // DuckDB-WASM butuh top-level await
    chunkSizeWarningLimit: 1500,
  },
  optimizeDeps: {
    exclude: ["@duckdb/duckdb-wasm"],
  },
});
