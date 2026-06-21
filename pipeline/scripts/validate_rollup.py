"""Confidence check: does the hourly->daily rollup reproduce the stored /days-derived daily
tier on overlapping days? Run before trusting the cutover.

Usage: pipeline/.venv/bin/python scripts/validate_rollup.py --data-dir /path/to/data
Reads <data-dir>/recent/*.parquet (hourly, wide) and <data-dir>/history/*.parquet (daily, wide),
re-derives the daily mean per (city, IST-day, pollutant) from the hourly rows, and compares to the
stored daily value. Prints match rate within tolerance.
"""
import argparse

import polars as pl

POLLUTANTS = ["pm25", "pm10", "no2", "so2", "o3", "co", "nh3"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--min-hours", type=int, default=18)
    ap.add_argument("--tol", type=float, default=0.10, help="relative tolerance")
    args = ap.parse_args()

    recent = pl.read_parquet(f"{args.data_dir}/recent/*.parquet")
    history = pl.read_parquet(f"{args.data_dir}/history/*.parquet")

    # IST local date from the UTC instant.
    recent = recent.with_columns(
        (pl.col("datetime_utc").str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%SZ", strict=False)
         .dt.replace_time_zone("UTC").dt.convert_time_zone("Asia/Kolkata")
         .dt.date().cast(pl.Utf8)).alias("ist_date"))

    checked = matched = 0
    for p in POLLUTANTS:
        if p not in recent.columns or p not in history.columns:
            continue
        roll = (recent.filter(pl.col(p).is_not_null())
                .group_by(["city", "ist_date"])
                .agg(pl.col(p).mean().alias("roll"), pl.len().alias("hours"))
                .filter(pl.col("hours") >= args.min_hours))
        stored = history.select(["city", "date", p]).rename({"date": "ist_date", p: "stored"})
        j = roll.join(stored, on=["city", "ist_date"], how="inner").filter(
            pl.col("stored").is_not_null())
        if j.height == 0:
            continue
        j = j.with_columns(
            ((pl.col("roll") - pl.col("stored")).abs()
             / pl.max_horizontal(pl.col("stored").abs(), pl.lit(1.0))).alias("rel"))
        ok = j.filter(pl.col("rel") <= args.tol).height
        checked += j.height
        matched += ok
        print(f"  {p:5}: {ok}/{j.height} within {args.tol:.0%} "
              f"(median rel={j['rel'].median():.3f})")

    if checked:
        print(f"\nOVERALL: {matched}/{checked} ({matched / checked:.1%}) within tolerance")
    else:
        print("\nNo overlapping (city, day, pollutant) rows to compare.")


if __name__ == "__main__":
    main()
