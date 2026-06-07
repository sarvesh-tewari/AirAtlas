# SETUP.md — Getting the dashboard running

Companion to `PLAN.md`. This is the **manual setup checklist** — the things only *you* can
do (accounts, keys, logins) plus the hosting decision. Everything else is built by Claude Code.

**How to use this with Claude Code:** open the repo in Claude Code, point it at `PLAN.md` and
this file, and tick the boxes below as you complete each step. Claude Code can do everything in
Part C; you handle Part A; Part B is a one-time decision.

---

## Division of labor

| You (manual) | Claude Code (delegated) |
|---|---|
| Create 2 API keys; install runtimes; log into GitHub once; paste secrets; enable hosting | Scaffold repo, write all code + tests, ingestion, pipeline, GitHub Actions workflows, frontend + widgets, deploy config |

There is **no OAuth app to register** anywhere. The only browser login is signing into GitHub
itself. The two API keys are simple copy-paste tokens.

---

## Part A — What only you can do (≈20–30 min, one-time)

### A1. Get the two API keys (Open-Meteo needs none)
- [ ] **data.gov.in (CPCB):** register a free account at data.gov.in (supports SSO/DigiLocker),
      open the **"Real time Air Quality Index from various locations"** resource, and copy your
      **API key** from your account profile. → this is the official live CPCB feed.
- [ ] **OpenAQ:** create a free account (see docs.openaq.org), then **generate an API key**.
      → this is the v3 requirement for historical data.
- [ ] **Open-Meteo:** nothing to do — no key required.

### A2. Install local runtimes (skip any already installed)
- [ ] **Python 3.11+** (the data pipeline)
- [ ] **Node.js 20 LTS** (the frontend)
- [ ] **Git**
- [ ] **GitHub CLI (`gh`)** — optional but recommended; lets Claude Code create the repo & enable
      hosting for you
- [ ] **Claude Code** — already installed

### A3. Authenticate GitHub once
- [ ] Run `gh auth login` (a one-time browser login). After this, Claude Code can create the repo,
      push code, and enable Pages — removing most manual GitHub clicking.

### A4. Store the keys as secrets (the step people forget)
The scheduled jobs run in GitHub's cloud, so the keys must live there too — not just on your laptop.
- [ ] In the repo: **Settings → Secrets and variables → Actions → New repository secret**.
      Add two, using these exact names (tell Claude Code to use the same names in the workflows):
      - `DATA_GOV_IN_KEY`
      - `OPENAQ_API_KEY`
- [ ] Create a local **`.env`** file with the same two keys for local testing.
      Claude Code will add `.env` to `.gitignore` — **never commit real keys.**

### A5. Enable hosting
- [ ] Pick a host (see **Part B**) and enable it. If GitHub Pages:
      **Settings → Pages → Build and deployment → Source → GitHub Actions.**

---

## Part B — Hosting: choosing & enabling

All three below host *static sites* (your dashboard is static: HTML/JS/CSS + data files, no
server). They differ on speed, limits, licensing, and setup friction. Verified June 2026.

| | GitHub Pages | Cloudflare Pages | Vercel (Hobby) |
|---|---|---|---|
| Cost | Free | Free | Free |
| Bandwidth | ~100 GB/mo (soft) | **Unlimited** | 100 GB/mo (hard cap) |
| On exceeding limit | Soft-throttle | n/a (unlimited) | **Site pauses** until reset |
| Commercial use | OK (project sites) | **OK** | **Not allowed** (Pro $20/mo) |
| Speed for India | Slowest of 3 | **Fastest** (300+ edges) | Fast |
| Setup friction | **Lowest** (repo-native, no new account) | Account + authorize GitHub | Account + authorize GitHub |
| Dev dashboard / previews | Minimal | Good | **Best** |
| Extra account needed | No | Yes (Cloudflare) | Yes (Vercel) |

**Is Vercel a hosting option?** Yes — same category as the others, just most associated with
Next.js. For a *static* site its serverless advantage is irrelevant, and its free tier is
non-commercial-only with hard caps that take the site offline under a traffic spike — a real risk
for a public dashboard. So it's an excellent tool, but the wrong fit here.

**Recommendation:**
- **Simplest start → GitHub Pages.** Zero extra accounts; integrates with the same GitHub Actions
  pipeline that refreshes data. Best for getting live fast.
- **Best long-term home → Cloudflare Pages.** Fastest for Indian users, truly unlimited bandwidth
  (matters if the dashboard gets popular), commercial-use safe. Costs one extra account + a
  one-time GitHub authorization.
- A clean migration path: launch on GitHub Pages, switch to Cloudflare Pages later if you want more
  speed/headroom. Decide now only which one to enable in **A5**.

> Whichever you choose, Claude Code writes the deploy workflow; your manual part is just enabling
> the host and (for Cloudflare/Vercel) authorizing it to read your repo.

---

## Part C — What Claude Code does (no action from you)

- Scaffold the repo, licences (`LICENSE` MIT/Apache-2.0, `LICENSE-DATA` CC BY 4.0), `SOURCES.md`.
- Build the AQI engine (NAQI + US + EU) with unit tests incl. the §7 regression case.
- Write the three ingestion scripts (CPCB, OpenAQ, Open-Meteo) and the transform/reconciliation logic.
- Write the two **GitHub Actions** workflows (hourly + daily) that reference your secrets by name.
- Build the **React/Vite frontend** and all widgets (map, headline + standard toggle, per-pollutant
  view, multi-year trend, exceedance analytics, weather overlay, compare cities, methodology).
- With `gh` authenticated: create the public repo, push, and configure the deploy.

---

## Part D — Recommended order

1. [ ] Install runtimes → `gh auth login` (A2, A3)
2. [ ] Register data.gov.in + OpenAQ, copy both keys (A1)
3. [ ] Open Claude Code in an empty folder; hand it `PLAN.md` + this file; tell it the secret names
4. [ ] Let it build Phases 1–2 and create + push the repo
5. [ ] Add the two GitHub secrets + create local `.env` (A4)
6. [ ] Choose + enable hosting (Part B, A5)
7. [ ] Let it finish the remaining phases
8. [ ] Verify the scheduled refresh runs green and the site is live

---

## Reference

**Secret names (must match the workflows):**
`DATA_GOV_IN_KEY`, `OPENAQ_API_KEY`

**Sources:**
- CPCB live → data.gov.in ("Real time Air Quality Index from various locations") — API key
- History → OpenAQ (docs.openaq.org) — API key
- Weather → Open-Meteo (open-meteo.com) — no key

**Golden rule:** never commit real keys. They live only in GitHub Actions secrets and your local
`.env` (gitignored).
