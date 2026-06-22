import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Map as MapIcon } from "lucide-react";
import { SectionTitle } from "./SectionTitle";
import { bandForIndex, bandByLabel, STANDARDS, type StandardId } from "../lib/standards";
import type { CityIndex } from "../lib/data";
import { isStale } from "../lib/freshness";
function colorFor(c: CityIndex, standard: StandardId): string {
  if (standard === "eu") return c.eu_band ? bandByLabel("eu", c.eu_band).color : "#9095a0";
  const idx = standard === "naqi" ? c.naqi : c.us;
  return idx != null ? bandForIndex(standard, idx).color : "#9095a0";
}

export function MapView({
  cities,
  standard,
  current,
  onCity,
  dark,
}: {
  cities: CityIndex[];
  standard: StandardId;
  current: string;
  onCity: (c: string) => void;
  dark: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const tileRef = useRef<L.TileLayer | null>(null);

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = L.map(ref.current, {
      scrollWheelZoom: true,
      attributionControl: true,
    }).setView([22.6, 79], 4);
    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Basemap (light/dark).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (tileRef.current) tileRef.current.remove();
    const url = dark
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
    tileRef.current = L.tileLayer(url, {
      attribution: "© OpenStreetMap, © CARTO",
      maxZoom: 10,
    }).addTo(map);
  }, [dark]);

  // Markers.
  useEffect(() => {
    const lg = layerRef.current;
    if (!lg) return;
    lg.clearLayers();
    for (const c of cities) {
      if (c.lat == null || c.lon == null) continue;
      const stale = isStale(c.last_date);
      const m = L.circleMarker([c.lat, c.lon], {
        radius: c.city === current ? 9 : 6,
        fillColor: stale ? "#9095a0" : colorFor(c, standard),
        color: stale
          ? "rgba(255,255,255,0.35)"
          : c.city === current
            ? "#fff"
            : "rgba(255,255,255,0.7)",
        weight: c.city === current ? 2.5 : 1.5,
        fillOpacity: stale ? 0.45 : 0.9,
      });
      const idx = standard === "eu" ? c.eu_band : standard === "naqi" ? c.naqi : c.us;
      m.bindTooltip(`${c.city}${idx != null ? ` · ${idx}` : ""}${stale ? " · stale data" : ""}`, {
        direction: "top",
      });
      m.on("click", () => onCity(c.city));
      m.addTo(lg);
    }
  }, [cities, standard, current, onCity]);

  return (
    // relative z-0 gives the map its own stacking context so Leaflet's panes/controls (z-index up
    // to ~1000) stay confined below the sticky topbar (z-20) instead of painting over the filters.
    // Clip the map element (not the section) so the info tooltip can overflow the card.
    <section className="card relative z-0">
      <div className="relative z-10 flex items-center justify-between px-5 pt-4">
        <SectionTitle
          icon={MapIcon}
          color="#2563eb"
          eyebrow="Coverage"
          info={
            <>
              Each dot is a city, coloured by its latest {standard.toUpperCase()} AQI category.
              Click a dot to load that city.
              <span className="mt-2 flex flex-col gap-1">
                {STANDARDS[standard].bands.map((b) => (
                  <span key={b.label} className="flex items-center gap-2">
                    <span
                      className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ background: b.color }}
                      aria-hidden
                    />
                    {b.label}
                  </span>
                ))}
                <span className="flex items-center gap-2">
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: "#9095a0" }}
                    aria-hidden
                  />
                  No current reading
                </span>

                <span className="flex items-center gap-2">
                  <span
                    className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: "#9095a0", opacity: 0.45 }}
                    aria-hidden
                  />
                  Stale monitor (&gt;30 days old)
                </span>
              </span>
            </>
          }
        >
          Map
        </SectionTitle>
        <span className="text-xs text-muted">
          click a city · coloured by {standard.toUpperCase()}
        </span>
      </div>
      <div
        ref={ref}
        className="relative z-0 mt-3 h-[360px] w-full overflow-hidden rounded-b-[1rem]"
        style={{ background: dark ? "#0f1216" : "#eef0f2" }}
      />
    </section>
  );
}
