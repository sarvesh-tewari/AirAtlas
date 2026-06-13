import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

// Section header: an uppercase eyebrow kicker over a heavy heading with a small colored icon chip.
export function SectionTitle({ icon: Icon, children, color = "var(--accent)", eyebrow }: {
  icon: LucideIcon; children: ReactNode; color?: string; eyebrow?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      {eyebrow && <span className="eyebrow self-start">{eyebrow}</span>}
      <h2 className="flex items-center gap-2.5 font-display text-[22px]">
        <span
          className="inline-flex h-7 w-7 items-center justify-center rounded-lg"
          style={{ background: `${color}1f`, color }}
        >
          <Icon size={16} strokeWidth={2.2} aria-hidden />
        </span>
        {children}
      </h2>
    </div>
  );
}
