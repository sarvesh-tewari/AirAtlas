// DuckDB-WASM bootstrap + Parquet query helper. The published per-city Parquet files are
// queried directly in the browser — no backend. Bundles load from jsDelivr (CSP-friendly).

import * as duckdb from "@duckdb/duckdb-wasm";

let dbPromise: Promise<duckdb.AsyncDuckDB> | null = null;

async function init(): Promise<duckdb.AsyncDuckDB> {
  const bundles = duckdb.getJsDelivrBundles();
  const bundle = await duckdb.selectBundle(bundles);
  const workerUrl = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker}");`], { type: "text/javascript" }),
  );
  const worker = new Worker(workerUrl);
  const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(), worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  URL.revokeObjectURL(workerUrl);
  return db;
}

export function getDB(): Promise<duckdb.AsyncDuckDB> {
  if (!dbPromise) dbPromise = init();
  return dbPromise;
}

// Query a remote Parquet URL and return plain row objects.
export async function queryParquet<T = Record<string, unknown>>(
  url: string,
  sql: (table: string) => string,
): Promise<T[]> {
  const db = await getDB();
  const name = url.split("/").pop() ?? "data.parquet";
  await db.registerFileURL(name, url, duckdb.DuckDBDataProtocol.HTTP, false);
  const conn = await db.connect();
  try {
    const result = await conn.query(sql(`read_parquet('${name}')`));
    // Arrow returns 64-bit ints as BigInt; coerce to Number for plain JS math.
    return result.toArray().map((r) => {
      const o = r.toJSON() as Record<string, unknown>;
      for (const k in o) if (typeof o[k] === "bigint") o[k] = Number(o[k]);
      return o as T;
    });
  } finally {
    await conn.close();
  }
}
