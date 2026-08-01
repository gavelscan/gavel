"use client";

/**
 * The record itself: every launch as a row you can scan, filter and open.
 *
 * A ledger, not a card grid. Rows are ruled, figures are monospaced and
 * right-aligned where they are comparable, and the ceiling column is the
 * only place colour appears — so the eye lands on risk, not on chrome.
 */

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  CEILING_TONE,
  LaunchRow,
  STATE_LABEL,
  STATE_TONE,
  pct,
  safeSymbol,
  shortAddr,
} from "@/lib/feed";

type Filter = "all" | LaunchRow["state"] | "flagged";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "all" },
  { key: "live", label: "in auction" },
  { key: "pool", label: "became a pool" },
  { key: "failed", label: "migration failed" },
  { key: "silent", label: "never migrated" },
  { key: "flagged", label: "ceiling not PASS" },
];

const PAGE = 60;

export default function LaunchTable({ rows }: { rows: LaunchRow[] }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (filter === "flagged" && r.ceiling === "PASS") return false;
      if (filter !== "all" && filter !== "flagged" && r.state !== filter)
        return false;
      if (!q) return true;
      return (
        (r.sym ?? "").toLowerCase().includes(q) ||
        (r.cur_sym ?? "").toLowerCase().includes(q) ||
        r.token.toLowerCase().includes(q) ||
        r.recipient.toLowerCase().includes(q)
      );
    });
  }, [rows, filter, query]);

  const visible = filtered.slice(0, shown);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-3">
        {FILTERS.map((f) => {
          const on = filter === f.key;
          return (
            <button
              key={f.key}
              onClick={() => {
                setFilter(f.key);
                setShown(PAGE);
              }}
              className="data border px-3 py-1.5 text-[11px] tracking-[0.1em] transition-colors"
              style={{
                borderColor: on ? "var(--brass)" : "var(--hairline)",
                color: on ? "var(--brass)" : "var(--ink-soft)",
                background: on ? "rgba(185,141,43,0.06)" : "transparent",
              }}
            >
              {f.label}
            </button>
          );
        })}
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShown(PAGE);
          }}
          placeholder="symbol or address"
          aria-label="Search launches by symbol or address"
          className="data ml-auto w-full max-w-[16rem] border px-3 py-1.5 text-[12px] outline-none"
          style={{
            borderColor: "var(--hairline)",
            background: "transparent",
            color: "var(--ink)",
          }}
        />
      </div>

      <p className="data mt-5 text-[11px] tracking-[0.12em] text-ink-soft">
        {filtered.length.toLocaleString("en-US")} OF{" "}
        {rows.length.toLocaleString("en-US")} LAUNCHES
      </p>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[62rem] border-collapse">
          <thead>
            <tr className="border-y border-hairline">
              {[
                "token",
                "priced in",
                "recipient",
                "LP reserve",
                "outcome",
                "ceiling",
                "block",
              ].map((h, i) => (
                <th
                  key={h}
                  className="eyebrow py-3 text-left font-normal"
                  style={{ textAlign: i >= 3 && i !== 4 ? "right" : "left" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr
                key={r.ini}
                className="group border-b border-hairline transition-colors hover:bg-[rgba(185,141,43,0.045)]"
              >
                <td className="py-3.5 pr-4">
                  <Link
                    href={`/launch/${r.ini}`}
                    className="data text-[14px] text-ink underline-offset-4 group-hover:underline"
                  >
                    {safeSymbol(r.sym)}
                  </Link>
                  <div className="data mt-0.5 text-[11px] text-ink-soft">
                    {shortAddr(r.token)}
                  </div>
                </td>
                <td className="py-3.5 pr-4">
                  <span className="data text-[13px]">
                    {safeSymbol(r.cur_sym)}
                  </span>
                  {r.cur_official && (
                    <span
                      className="data ml-2 text-[10px] tracking-[0.1em]"
                      style={{ color: "var(--pass)" }}
                      title="Address is in the official Robinhood issuer registry"
                    >
                      OFFICIAL
                    </span>
                  )}
                </td>
                <td className="data py-3.5 pr-4 text-[12px] text-ink-soft">
                  {shortAddr(r.recipient)}
                  <span className="ml-2 text-[11px]">
                    {r.rec_code > 0
                      ? "contract"
                      : r.rec_nonce === 0
                        ? "fresh EOA"
                        : "EOA"}
                  </span>
                </td>
                <td className="data py-3.5 pr-4 text-right text-[13px]">
                  {pct(r.lp_ratio)}
                </td>
                <td className="py-3.5 pr-4">
                  <span className="flex items-center gap-2">
                    <span
                      aria-hidden
                      className="block h-[11px] w-[3px]"
                      style={{ background: STATE_TONE[r.state] }}
                    />
                    <span className="data text-[12px] text-ink-soft">
                      {STATE_LABEL[r.state]}
                    </span>
                  </span>
                </td>
                <td className="py-3.5 pr-4 text-right">
                  <span
                    className="data border px-2 py-0.5 text-[11px] tracking-[0.12em]"
                    style={{
                      color: CEILING_TONE[r.ceiling],
                      borderColor: CEILING_TONE[r.ceiling],
                    }}
                  >
                    {r.ceiling}
                  </span>
                </td>
                <td className="data py-3.5 text-right text-[12px] text-ink-soft">
                  {r.block.toLocaleString("en-US")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {visible.length === 0 && (
        <p className="mt-10 text-ink-soft">
          No launch matches that filter. Clear the search to see the whole
          record.
        </p>
      )}

      {shown < filtered.length && (
        <button
          onClick={() => setShown((s) => s + PAGE)}
          className="data mt-10 border px-5 py-2.5 text-[12px] tracking-[0.12em] transition-colors hover:border-brass hover:text-brass"
          style={{ borderColor: "var(--hairline)", color: "var(--ink-soft)" }}
        >
          SHOW {Math.min(PAGE, filtered.length - shown)} MORE
        </button>
      )}
    </div>
  );
}
