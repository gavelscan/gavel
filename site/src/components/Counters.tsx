"use client";

/**
 * The four archive figures, kept honest.
 *
 * These numbers are baked into the page at build time, so without this they
 * would sit at whatever they were when the site last deployed — which is
 * exactly the frozen-dashboard problem the record is supposed to avoid.
 * The component polls the same public endpoint anyone else can call
 * (/v1/summary.json, rewritten every refresh) and flips the digits that
 * moved. If the endpoint is unreachable the build-time figures stay on
 * screen unchanged: a stale true number beats a blank.
 */

import { useEffect, useState } from "react";
import Reveal from "./Reveal";
import SplitFlap from "./SplitFlap";

type Summary = {
  archived_events: number;
  launches: number;
  token_paired: number;
  by_state: Record<string, number>;
};

export type CounterSeed = {
  events: number;
  total: number;
  tokenPaired: number;
  unfilled: number;
};

const POLL_MS = 60_000;

export default function Counters({ seed }: { seed: CounterSeed }) {
  const [n, setN] = useState(seed);

  useEffect(() => {
    let alive = true;

    async function read() {
      try {
        const r = await fetch("/v1/summary.json", { cache: "no-store" });
        if (!r.ok) return;
        const s: Summary = await r.json();
        if (!alive || typeof s.archived_events !== "number") return;
        setN({
          events: s.archived_events,
          total: s.launches,
          tokenPaired: s.token_paired,
          unfilled: s.by_state?.unfilled ?? 0,
        });
      } catch {
        // Offline, or the file is mid-write. Keep the last good figures.
      }
    }

    read();
    const id = setInterval(read, POLL_MS);
    const onFocus = () => read();
    window.addEventListener("focus", onFocus);
    return () => {
      alive = false;
      clearInterval(id);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  const cells: [string, number][] = [
    ["Archived events", n.events],
    ["Launch auctions", n.total],
    ["Token-paired", n.tokenPaired],
    ["Drew no bids", n.unfilled],
  ];

  return (
    <div className="mt-16 grid gap-px border border-hairline bg-hairline sm:grid-cols-4">
      {cells.map(([label, value], i) => (
        <Reveal key={label} delay={i * 0.06} className="bg-paper">
          <div className="p-6">
            <SplitFlap
              value={value}
              className="data block text-[clamp(1.8rem,3vw,2.6rem)] leading-none"
            />
            <div className="eyebrow mt-3">{label}</div>
          </div>
        </Reveal>
      ))}
    </div>
  );
}
