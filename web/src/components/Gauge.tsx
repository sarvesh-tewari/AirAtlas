// Approved AQI headline: a coloured arc gauge with the index + category in the centre.
// Numeric standards (NAQI, US) only; EU renders as a band chip elsewhere.

import { STANDARDS, bandForIndex, type StandardId } from "../lib/standards";

function polar(cx: number, cy: number, r: number, deg: number): [number, number] {
  const a = (deg * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
}

export function Gauge({ standard, index }: { standard: StandardId; index: number }) {
  const cfg = STANDARDS[standard];
  const cx = 120, cy = 128, r = 92;
  const v2deg = (v: number) => 180 * (1 - Math.max(0, Math.min(cfg.max, v)) / cfg.max);
  const arc = (d1: number, d2: number) => {
    const [x1, y1] = polar(cx, cy, r, d1);
    const [x2, y2] = polar(cx, cy, r, d2);
    return `M${x1} ${y1} A${r} ${r} 0 ${d1 - d2 > 180 ? 1 : 0} 1 ${x2} ${y2}`;
  };

  let lo = 0;
  const segs = cfg.bands.map((b) => {
    const seg = { d: arc(v2deg(lo), v2deg(b.max ?? cfg.max)), color: b.color };
    lo = b.max ?? cfg.max;
    return seg;
  });
  const band = bandForIndex(standard, index);
  const [px, py] = polar(cx, cy, r, v2deg(index));

  return (
    <svg viewBox="0 0 240 150" className="w-full max-w-[260px]" role="img" aria-label={`AQI ${index}, ${band.label}`}>
      {segs.map((s, i) => (
        <path key={i} d={s.d} stroke={s.color} strokeWidth={15} fill="none" />
      ))}
      <circle cx={px} cy={py} r={8} fill="var(--gauge-dot-bg)" stroke={band.color} strokeWidth={4} />
      <text
        x={cx} y={cy - 4} textAnchor="middle" fontSize={46} fill="currentColor"
        fontFamily="var(--font-sans)" fontWeight={600} style={{ letterSpacing: "-0.03em" }}
      >
        {index}
      </text>
      <text x={cx} y={cy + 17} textAnchor="middle" fontSize={14} fontWeight={500} fill={band.color}>
        {band.label}
      </text>
    </svg>
  );
}
