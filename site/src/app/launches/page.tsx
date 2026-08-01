import type { Metadata } from "next";
import LaunchTable from "@/components/LaunchTable";
import { ROWS, FEED } from "@/lib/feed";

export const metadata: Metadata = {
  title: "Launches — GAVEL",
  description:
    "Every launch auction recorded on Robinhood Chain, with the deterministic verdict ceiling for each one.",
};

const count = (s: string) => ROWS.filter((r) => r.state === s).length;

export default function Launches() {
  const notPass = ROWS.filter((r) => r.ceiling !== "PASS").length;

  return (
    <main className="bg-paper-warm grain min-h-screen px-6 pb-28 pt-32 sm:px-10">
      <div className="mx-auto max-w-6xl">
        <p className="eyebrow mb-6">The record · Robinhood Chain</p>
        <h1 className="display max-w-[20ch] text-[clamp(2.2rem,5vw,3.6rem)]">
          Every launch auction, and what the parameters say about it.
        </h1>
        <p className="mt-7 max-w-[62ch] text-ink-soft">
          Each row is one auction created through Uniswap&rsquo;s Liquidity
          Launcher, read straight from the chain. The ceiling is what the
          deterministic checks allow — a judged verdict can sit at the ceiling
          or below it, never above.
        </p>

        <dl className="mt-12 grid gap-px border border-hairline bg-hairline sm:grid-cols-4">
          {[
            ["Launches", ROWS.length],
            ["Became pools", count("pool")],
            ["Migration failed", count("failed")],
            ["Ceiling below PASS", notPass],
          ].map(([label, value]) => (
            <div key={String(label)} className="bg-paper p-5">
              <dd className="data text-[1.9rem] leading-none">
                {Number(value).toLocaleString("en-US")}
              </dd>
              <dt className="eyebrow mt-2.5">{String(label)}</dt>
            </div>
          ))}
        </dl>

        <div className="mt-16">
          <LaunchTable rows={ROWS} />
        </div>

        <p className="data mt-14 text-[11px] leading-relaxed text-ink-soft">
          Read at block {FEED.head.toLocaleString("en-US")}. Outcomes change as
          auctions close and migrations run; the record is rebuilt from chain
          state, never edited by hand.
        </p>
      </div>
    </main>
  );
}
