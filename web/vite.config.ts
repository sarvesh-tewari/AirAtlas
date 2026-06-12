import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// `base` is "/" in dev; GitHub Pages project sites need "/<repo>/" — set via env at deploy (Phase 10).
export default defineConfig({
  base: process.env.VITE_BASE ?? "/",
  plugins: [react(), tailwindcss()],
  // DuckDB-WASM ships a worker + wasm; don't pre-bundle it.
  optimizeDeps: { exclude: ["@duckdb/duckdb-wasm"] },
});
