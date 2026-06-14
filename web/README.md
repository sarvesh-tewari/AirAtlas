# web/ — React + Vite + TypeScript frontend

The single-page dashboard. Reads the published Parquet/JSON dataset and queries it
in-browser via DuckDB-WASM; charts with ECharts, map with Leaflet.

```
src/lib/         data access, AQI standards, DuckDB helpers, formatting
src/components/  gauge, map, charts, pollutant cards, comparison, etc.
src/pages/       dashboard + about
```

```bash
npm install
npm run dev      # local dev server (expects ../data via web/public/data symlink)
npm run build    # type-check + production build
```
