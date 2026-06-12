import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

// Section heading with a small accent-colored icon (part of the "category wash" color treatment).
export function SectionTitle({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <h2 className="flex items-center gap-2 font-display text-lg text-ink">
      <Icon size={18} className="text-accent" strokeWidth={2} aria-hidden />
      {children}
    </h2>
  );
}
