// Theme-aware chart colors (canvas can't read CSS vars). Kept out of EChart.tsx so that file
// only exports a component - mixing a component + a helper export breaks React Fast Refresh.
// Mirrors the design-system tokens.
export function chartTheme(dark: boolean) {
  return {
    label: dark ? "#94a3b8" : "#64748b", // --body
    axis: dark ? "rgba(255,255,255,0.14)" : "rgba(15,23,42,0.12)",
    split: dark ? "rgba(255,255,255,0.06)" : "rgba(15,23,42,0.06)",
    ink: dark ? "#f1f5f9" : "#0f172a", // --heading
    accent: dark ? "#6ba1ff" : "#3d7fe6", // --accent-text
    tooltipBg: dark ? "#131c2e" : "#ffffff", // --surface
  };
}
