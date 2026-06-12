import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Map as MapIcon } from "lucide-react";
import { SectionTitle } from "./SectionTitle";
import { bandForIndex, bandByLabel, type StandardId } from "../lib/standards";
import type { CityIndex } from "../lib/data";

function colorFor(c: CityIndex, standard: StandardId): string {
  if (standard === "eu") return c.eu_band ? bandByLabel("eu", c.eu_band).color : "#9095a0";
  const idx = standard === "naqi" ? c.naqi : c.us;
  return idx != null ? bandForIndex(standard, idx).color : "#9095a0";
}

export function MapView({ cities, standard, current, onCity, dark }: {
  cities: CityIndex[]; standard: StandardId; current: string; onCity: (c: string) => void; dark: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const tileRef = useRef<L.TileLayer | null>(null);

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = L.map(ref.current, { scrollWheelZoom: true, attributionControl: true }).setView([22.6, 79], 4);
    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // Basemap (light/dark).
  useEffect(() => {
    const map = mapRef.current; if (!map) return;
    if (tileRef.current) tileRef.current.remove();
    const url = dark
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
    tileRef.current = L.tileLayer(url, { attribution: "© OpenStreetMap, © CARTO", maxZoom: 10 }).addTo(map);
  }, [dark]);

  // Markers.
  useEffect(() => {
    const lg = layerRef.current; if (!lg) return;
    lg.clearLayers();
    for (const c of cities) {
      if (c.lat == null || c.lon == null) continue;
      const m = L.circleMarker([c.lat, c.lon], {
        radius: c.city === current ? 9 : 6,
        fillColor: colorFor(c, standard), color: c.city === current ? "#fff" : "rgba(255,255,255,0.7)",
        weight: c.city === current ? 2.5 : 1.5, fillOpacity: 0.9,
      });
      const idx = standard === "eu" ? c.eu_band : standard === "naqi" ? c.naqi : c.us;
      m.bindTooltip(`${c.city}${idx != null ? ` · ${idx}` : ""}`, { direction: "top" });
      m.on("click", () => onCity(c.city));
      m.addTo(lg);
    }
  }, [cities, standard, current, onCity]);

  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between px-5 pt-4">
        <SectionTitle icon={MapIcon}>Map</SectionTitle>
        <span className="text-xs text-faint">click a city · coloured by {standard.toUpperCase()}</span>
      </div>
      <div ref={ref} className="mt-3 h-[360px] w-full" style={{ background: dark ? "#0f1216" : "#eef0f2" }} />
    </section>
  );
}
