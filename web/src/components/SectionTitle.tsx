import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

// Section heading with a small colored icon in a tinted chip (adds per-section colour flavour).
export function SectionTitle({ icon: Icon, children, color = "var(--accent)" }: {
  icon: LucideIcon; children: ReactNode; color?: string;
}) {
  return (
    <h2 className="flex items-center gap-2.5 font-display text-lg text-ink">
      <span
        className="inline-flex h-7 w-7 items-center justify-center rounded-lg"
        style={{ background: `${color}1f`, color }}
      >
        <Icon size={16} strokeWidth={2.2} aria-hidden />
      </span>
      {children}
    </h2>
  );
}
