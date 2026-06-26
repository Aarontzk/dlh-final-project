import { defineConfig } from "vite";

// Repo di-deploy ke GitHub Pages project site:
//   https://aarontzk.github.io/dlh-final-project/
// Jadi base harus '/dlh-final-project/'. Override via env VITE_BASE saat lokal.
export default defineConfig({
  base: process.env.VITE_BASE ?? "/dlh-final-project/",
  build: {
    target: "esnext", // DuckDB-WASM butuh top-level await
    chunkSizeWarningLimit: 1500,
  },
  optimizeDeps: {
    exclude: ["@duckdb/duckdb-wasm"],
  },
});
