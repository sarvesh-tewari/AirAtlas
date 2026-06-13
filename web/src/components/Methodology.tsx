import { Logo } from "./Logo";

export function Methodology() {
  return (
    <div className="flex flex-col gap-5">
      <section className="card flex flex-col items-start gap-4 p-6">
        <Logo variant="lockup" className="text-[34px]" />
        <h1 className="font-display text-2xl text-heading">Methodology</h1>
        <p className="text-sm leading-relaxed text-body">
          AQI is a <em>formula, not a measurement</em>. AirAtlas stores raw pollutant concentrations and
          computes each standard on demand, so the same air can read differently across standards, by design.
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">The three standards</h2>
        <ul className="mt-2 space-y-2 text-sm leading-relaxed text-body">
          <li><span className="font-medium text-heading">India NAQI</span> (default) - CPCB 2014, 8 pollutants, 0–500, overall = worst sub-index.</li>
          <li><span className="font-medium text-heading">US EPA AQI</span> - effective May 2024; gases use ppb/ppm with short averaging windows.</li>
          <li><span className="font-medium text-heading">EU EAQI</span> - EEA 2024-revised bands (Good → Extremely Poor); a category, not a 0–500 number.</li>
        </ul>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">Sources & the today/history seam</h2>
        <p className="mt-2 text-sm leading-relaxed text-body">
          <span className="font-medium text-heading">Today</span> comes from CPCB (data.gov.in);
          <span className="font-medium text-heading"> history</span> (up to yesterday) from OpenAQ, which re-ingests the
          same CPCB stations. Weather is from Open-Meteo. Every view labels its source, and trend charts mark the seam.
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">City aggregation & exceedance</h2>
        <p className="mt-2 text-sm leading-relaxed text-body">
          A city's value is the mean concentration across its stations; AQI is computed from those concentrations
          identically for all three standards. Exceedance counts the days per year a city's daily AQI exceeds a
          standard-aware threshold. Thin-coverage cities are flagged.
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">Freshness & coverage</h2>
        <p className="mt-2 text-sm leading-relaxed text-body">
          Today's snapshot refreshes hourly; multi-year history updates daily. Station coverage
          varies. Cities with sparse history are flagged, and a city's NAQI needs at least three
          pollutants present (one being PM) to be valid. The site serves its own stored data, so
          it stays up even if an upstream source is temporarily down (the headline simply shows a
          "last updated" time and a staleness notice).
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">Open data</h2>
        <p className="mt-2 text-sm leading-relaxed text-body">
          The published per-city Parquet files <em>are</em> the open dataset, and anyone can download
          and query them. Column definitions and units are documented in the project's
          <code className="px-1">SOURCES.md</code> data dictionary.
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">Attribution</h2>
        <p className="mt-2 text-sm leading-relaxed text-body">
          Air-quality data © CPCB / data.gov.in and OpenAQ (CC BY); weather © Open-Meteo (CC BY 4.0).
          Code MIT, data CC BY 4.0.
        </p>
      </section>
    </div>
  );
}
