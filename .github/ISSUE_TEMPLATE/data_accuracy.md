---
name: "Data accuracy report"
about: "A city's reading looks wrong, implausible, or stale"
title: "[data] "
labels: ["data-quality"]
---

**City / location**
<!-- e.g. Mumbai -->

**What AirAtlas shows**
<!-- the value/category, which standard (NAQI / US / EU), and the date shown -->

**What you expected (and your source)**
<!-- e.g. aqi.in / CPCB showed X at <time>; link if possible -->

**Screenshot**
<!-- optional but very helpful -->

---
Before filing, a few things that are working as intended:
- AQI is a calculated index (not a measurement) and differs by standard for the same air.
- Data can lag ~1-2 days by nature.
- A city whose monitor has gone quiet is shown muted and clearly dated, not as current.
