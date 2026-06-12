export function Methodology() {
  return (
    <div className="flex flex-col gap-5">
      <section className="card p-6">
        <h1 className="font-display text-2xl text-ink">Methodology</h1>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          AQI is a <em>formula, not a measurement</em>. AirAtlas stores raw pollutant concentrations and
          computes each standard on demand, so the same air can read differently across standards — by design.
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-ink">The three standards</h2>
        <ul className="mt-2 space-y-2 text-sm leading-relaxed text-muted">
          <li><span className="font-medium text-ink">India NAQI</span> (default) — CPCB 2014, 8 pollutants, 0–500, overall = worst sub-index.</li>
          <li><span className="font-medium text-ink">US EPA AQI</span> — effective May 2024; gases use ppb/ppm with short averaging windows.</li>
          <li><span className="font-medium text-ink">EU EAQI</span> — EEA 2024-revised bands (Good → Extremely Poor); a category, not a 0–500 number.</li>
        </ul>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-ink">Sources & the today/history seam</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          <span className="font-medium text-ink">Today</span> comes from CPCB (data.gov.in);
          <span className="font-medium text-ink"> history</span> (up to yesterday) from OpenAQ, which re-ingests the
          same CPCB stations. Weather is from Open-Meteo. Every view labels its source, and trend charts mark the seam.
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-ink">City aggregation & exceedance</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          A city's value is the mean concentration across its stations; AQI is computed from those concentrations
          identically for all three standards. Exceedance counts the days per year a city's daily AQI exceeds a
          standard-aware threshold. Thin-coverage cities are flagged.
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-ink">Attribution</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Air-quality data © CPCB / data.gov.in and OpenAQ (CC BY); weather © Open-Meteo (CC BY 4.0).
          Code MIT, data CC BY 4.0.
        </p>
      </section>
    </div>
  );
}
