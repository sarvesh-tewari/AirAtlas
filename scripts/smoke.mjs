// Lightweight smoke / synthetic check for the live AirAtlas site.
// Verifies the deployed site is up, the app shell loads, and real data is present + fresh —
// the failures a build-time test can't catch (CDN/Pages broken, data branch gone, pipeline stalled).
//
//   node scripts/smoke.mjs [baseUrl]
//
// Exits non-zero (with a summary) if any check fails, after a few retries to ride out the
// brief CDN propagation window right after a deploy. Used by deploy.yml (post-deploy) and
// uptime.yml (scheduled synthetic check).

const BASE = (process.argv[2] || "https://sarvesh-tewari.github.io/AirAtlas/").replace(/\/?$/, "/");
const STALE_AFTER_DAYS = 4; // generated_today = "data through" (latest daily date); data lags ~1-2d by nature, older than this means a stalled pipeline.

const bust = (url) => `${url}${url.includes("?") ? "&" : "?"}cb=${Date.now()}`;

async function get(path, { json = false, binary = false } = {}) {
  const r = await fetch(bust(BASE + path), { redirect: "follow" });
  if (!r.ok) throw new Error(`HTTP ${r.status} for /${path}`);
  if (json) return r.json();
  if (binary) return new Uint8Array(await r.arrayBuffer());
  return r.text();
}

const CHECKS = [
  ["home page serves the app shell", async () => {
    const html = await get("");
    if (!html.includes('id="root"')) throw new Error("no #root element");
    if (!/assets\/index-[\w-]+\.js/.test(html)) throw new Error("no JS bundle reference");
  }],
  ["city list is populated", async () => {
    const j = await get("data/meta/city_list.json", { json: true });
    if (!Array.isArray(j.cities) || j.cities.length < 50)
      throw new Error(`only ${j.cities?.length ?? 0} cities`);
  }],
  ["city index (map/selector) is populated", async () => {
    const j = await get("data/meta/cities.json", { json: true });
    if (!Array.isArray(j) || j.length < 50) throw new Error(`only ${j?.length ?? 0} entries`);
  }],
  ["data is not stale", async () => {
    const j = await get("data/meta/city_list.json", { json: true });
    const gen = j.generated_today;
    if (!gen) throw new Error("no generated_today");
    const ageDays = Math.floor((Date.now() - new Date(`${gen}T00:00:00Z`).getTime()) / 8.64e7);
    if (ageDays > STALE_AFTER_DAYS) throw new Error(`last generated ${gen} (${ageDays} days ago)`);
  }],
  ["a sample city's Parquet loads", async () => {
    const buf = await get("data/history/delhi.parquet", { binary: true });
    if (buf.byteLength < 1000) throw new Error(`only ${buf.byteLength} bytes`);
  }],
];

async function runSuite() {
  const failures = [];
  for (const [name, fn] of CHECKS) {
    try {
      await fn();
      console.log(`  ok  ${name}`);
    } catch (e) {
      failures.push(`${name} -> ${e.message}`);
      console.log(`FAIL  ${name} -> ${e.message}`);
    }
  }
  return failures;
}

const RETRIES = 4;
let failures = [];
for (let attempt = 1; attempt <= RETRIES; attempt++) {
  console.log(`\nSmoke check ${BASE} (attempt ${attempt}/${RETRIES})`);
  failures = await runSuite();
  if (failures.length === 0) break;
  if (attempt < RETRIES) {
    console.log("  retrying in 15s (CDN may still be propagating)...");
    await new Promise((r) => setTimeout(r, 15000));
  }
}

if (failures.length) {
  console.error(`\n${failures.length} smoke check(s) FAILED:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log("\nAll smoke checks passed.");
