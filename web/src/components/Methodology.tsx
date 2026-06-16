import { Logo } from "./Logo";

export function Methodology() {
  return (
    <div className="flex flex-col gap-5">
      <section className="card flex flex-col items-start gap-4 p-6">
        <Logo variant="lockup" className="text-[34px]" />
        <h1 className="font-display text-2xl text-heading">About AirAtlas</h1>
        <p className="text-sm leading-relaxed text-body">
          An <span className="font-medium text-heading">Air Quality Index (AQI)</span> condenses
          several pollutants into one easy-to-read number or category. It is a <em>calculated index,
          not a direct measurement</em>: each region defines its own formula for turning pollutant
          concentrations into that number, so the very same air can read differently from one
          standard to the next.
        </p>
        <p className="text-sm leading-relaxed text-body">
          AirAtlas stores the raw concentrations and computes each standard on
          demand, so those differences are transparent rather than hidden.
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">How the index is calculated</h2>
        <p className="mt-2 text-sm leading-relaxed text-body">
          Monitors report raw concentrations for each pollutant (PM2.5, PM10, NO₂, SO₂, O₃, CO,
          NH₃), in µg/m³ (CO in mg/m³). Turning those into an AQI takes three steps:
        </p>
        <ol className="mt-3 space-y-2 text-sm leading-relaxed text-body">
          <li>
            <span className="font-medium text-heading">1. Sub-index per pollutant.</span> Each
            concentration is mapped to a 0 to 500 sub-index using the standard's breakpoint table, a
            piecewise-linear scale. For example, India's NAQI maps 0 to 30 µg/m³ of PM2.5 onto a 0 to
            50 "Good" sub-index, 31 to 60 onto "Satisfactory", and so on.
          </li>
          <li>
            <span className="font-medium text-heading">2. Overall AQI = the worst sub-index.</span>{" "}
            The single pollutant in the unhealthiest band sets the headline number; we label it the
            <span className="font-medium text-heading"> dominant pollutant</span>.
          </li>
          <li>
            <span className="font-medium text-heading">3. Averaging windows.</span> Each pollutant is
            averaged over the window its standard specifies (for example PM2.5 as a 24-hour mean,
            ozone over 8 or 1 hour) before the lookup.
          </li>
        </ol>
        <p className="mt-3 text-sm leading-relaxed text-body">
          Standards differ in both their breakpoints and their averaging windows, which is why the
          same air can read "Moderate" on one scale and "Unhealthy" on another.
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">The three standards</h2>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-body marker:text-muted">
          <li><span className="font-medium text-heading">India NAQI</span> (default), CPCB 2014: 8 pollutants, a 0 to 500 scale, overall = the worst sub-index.</li>
          <li><span className="font-medium text-heading">US EPA AQI</span>, effective May 2024: 6 pollutants, gases in ppb/ppm with short averaging windows.</li>
          <li><span className="font-medium text-heading">EU EAQI</span>, EEA 2024-revised: six bands (Good to Extremely Poor), a category rather than a 0 to 500 number.</li>
        </ul>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">Sources & the today/history seam</h2>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-body marker:text-muted">
          <li><span className="font-medium text-heading">Today</span> comes from CPCB (data.gov.in).</li>
          <li><span className="font-medium text-heading">History</span> (up to yesterday) comes from OpenAQ, which re-ingests the same CPCB stations.</li>
          <li><span className="font-medium text-heading">Weather</span> comes from Open-Meteo.</li>
        </ul>
        <p className="mt-3 text-sm leading-relaxed text-body">
          Every view labels its source, and trend charts mark the seam between today and history.
        </p>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">City aggregation & exceedance</h2>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-body marker:text-muted">
          <li>A city's value is the <span className="font-medium text-heading">median</span> concentration across its stations (the median, not the mean, so one faulty monitor cannot skew the whole city).</li>
          <li>AQI is computed from those concentrations identically for all three standards.</li>
          <li>Exceedance counts the days per year a city's daily AQI passes a standard-aware threshold.</li>
          <li>Thin-coverage cities are flagged.</li>
        </ul>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">Freshness & coverage</h2>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-body marker:text-muted">
          <li>Today's snapshot refreshes hourly; multi-year history updates daily.</li>
          <li>A city's NAQI needs at least three pollutants present (one being PM) to be valid.</li>
          <li>The site serves its own stored data, so it stays up even if an upstream source is temporarily down (the headline shows a "last updated" time and a staleness notice).</li>
          <li>Each city shows how recent its data is. When a city's most recent valid reading is more than 30 days old (a monitor that has gone quiet), it is shown muted and clearly dated rather than presented as current.</li>
        </ul>
      </section>

      <section className="card p-6">
        <h2 className="font-display text-lg text-heading">Sensor-fault filtering</h2>
        <p className="mt-2 text-sm leading-relaxed text-body">
          Real-world monitors produce bad data: out-of-range spikes, device error codes, and
          sensors that freeze on a single value. We drop physically impossible readings (and
          known error codes) before computing any index, and we discard values that repeat
          <em> identically for three or more days</em> in either direction (a stuck-high reading
          faking "Severe" or a stuck-zero faking "clean"), since genuine air quality always varies.
          City values use the median across a city's stations, so one faulty monitor cannot skew
          the whole city.
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
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-body marker:text-muted">
          <li>Air-quality data © CPCB / data.gov.in and OpenAQ (CC BY).</li>
          <li>Weather © Open-Meteo (CC BY 4.0).</li>
          <li>Code under MIT; data under CC BY 4.0.</li>
        </ul>
      </section>
    </div>
  );
}
