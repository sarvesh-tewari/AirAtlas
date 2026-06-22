import { Info, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

// A small muted "i" that reveals an explanatory tooltip on hover/focus (keyboard-accessible).
// Same pattern as the standard-toggle help in the top bar.
export function InfoDot({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        aria-label={label ?? "What is this?"}
        className="rounded-full p-0.5 text-muted transition-colors hover:text-heading focus-visible:text-heading"
      >
        <Info size={15} aria-hidden />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-30 mt-2 w-72 rounded-lg border border-border bg-surface p-3 text-left text-xs font-normal leading-relaxed text-body opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {children}
      </span>
    </span>
  );
}

// Section header: an uppercase eyebrow kicker over a heavy heading with a small colored icon chip,
// plus an optional "i" info tooltip.
export function SectionTitle({
  icon: Icon,
  children,
  color = "var(--accent)",
  eyebrow,
  info,
}: {
  icon: LucideIcon;
  children: ReactNode;
  color?: string;
  eyebrow?: string;
  info?: ReactNode;
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
        {info && (
          <InfoDot label={typeof children === "string" ? `About: ${children}` : undefined}>
            {info}
          </InfoDot>
        )}
      </h2>
    </div>
  );
}
