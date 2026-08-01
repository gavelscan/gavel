"use client";

/**
 * An address you can actually take with you.
 *
 * Every address on this site is something a reader may want to paste
 * somewhere else — a wallet, an explorer, a scanner. Showing a truncated
 * form and making them retype it is the sort of small hostility that adds
 * up, so the full value is always one click away and the button says so
 * after it has copied.
 */

import { useCallback, useState } from "react";

export default function Copyable({
  value,
  label,
  className = "",
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Clipboard is blocked in some contexts; fall back to a selection
      // the reader can copy by hand rather than failing silently.
      const el = document.createElement("textarea");
      el.value = value;
      document.body.appendChild(el);
      el.select();
      try {
        document.execCommand("copy");
      } finally {
        document.body.removeChild(el);
      }
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  }, [value]);

  return (
    <button
      type="button"
      onClick={copy}
      title={value}
      aria-label={`Copy ${label ?? "address"} ${value}`}
      className={`group inline-flex items-center gap-1.5 transition-colors hover:text-brass ${className}`}
    >
      <span>{label ?? value}</span>
      <span
        aria-hidden
        className="data text-[10px] tracking-[0.1em] opacity-0 transition-opacity group-hover:opacity-70"
        style={{ opacity: copied ? 1 : undefined, color: copied ? "var(--pass)" : undefined }}
      >
        {copied ? "COPIED" : "COPY"}
      </span>
    </button>
  );
}
