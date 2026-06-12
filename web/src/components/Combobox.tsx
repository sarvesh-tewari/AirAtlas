// Searchable, keyboard-navigable single-select combobox (type to filter). Used for every
// dropdown in the app per the design requirement.

import { useEffect, useId, useMemo, useRef, useState } from "react";

export interface Option {
  value: string;
  label: string;
  hint?: string;
}

export function Combobox({
  value,
  options,
  onChange,
  placeholder = "Search…",
  ariaLabel,
  triggerLabel,
}: {
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  placeholder?: string;
  ariaLabel?: string;
  triggerLabel?: string; // override the button text (e.g. "+ Add city" for an add-picker)
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const selected = options.find((o) => o.value === value);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [query, options]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function commit(v: string) {
    onChange(v);
    setOpen(false);
    setQuery("");
  }

  function onKey(e: React.KeyboardEvent) {
    if (!open && (e.key === "ArrowDown" || e.key === "Enter")) {
      setOpen(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered[active]) commit(filtered[active].value);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-label={ariaLabel}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm hover:bg-surface-2"
      >
        <span className="font-medium text-ink">{triggerLabel ?? selected?.label ?? "Select"}</span>
        <span className="text-faint" aria-hidden>▾</span>
      </button>

      {open && (
        <div className="absolute z-30 mt-1 w-64 overflow-hidden rounded-xl border border-border bg-surface shadow-lg">
          <input
            autoFocus
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKey}
            placeholder={placeholder}
            aria-label={ariaLabel ?? "Search"}
            aria-controls={listId}
            className="w-full border-b border-border bg-transparent px-3 py-2 text-sm outline-none placeholder:text-faint"
          />
          <ul id={listId} role="listbox" className="max-h-64 overflow-auto py-1">
            {filtered.length === 0 && (
              <li className="px-3 py-2 text-sm text-muted">No matches</li>
            )}
            {filtered.map((o, i) => (
              <li
                key={o.value}
                role="option"
                aria-selected={o.value === value}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  commit(o.value);
                }}
                className={`flex cursor-pointer items-center justify-between px-3 py-2 text-sm ${
                  i === active ? "bg-surface-2" : ""
                } ${o.value === value ? "text-accent" : "text-ink"}`}
              >
                <span>{o.label}</span>
                {o.hint && <span className="text-xs text-faint">{o.hint}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
