import type { Metadata } from "next";
import Link from "next/link";
import { CEILING_TONE, FEED, ROWS, pct, safeSymbol, shortAddr } from "@/lib/feed";

export const metadata: Metadata = {
  title: "Live auctions — GAVEL",
  description:
    "Launch auctions on Robinhood Chain that have not yet reached their migration block.",
};

/* Robinhood Chain targets sub-second blocks. This is used only to turn a
   block distance into a rough human interval, and it is labelled as rough. */
const SECONDS_PER_BLOCK = 0.25;

function remaining(blocks: number) {
  if (blocks <= 0) return "any moment";
  const s = blocks * SECONDS_PER_BLOCK;
  if (s < 90) return "under two minutes";
  if (s < 5400) return `about ${Math.round(s / 60)} minutes`;
  if (s < 172800) return `about ${Math.round(s / 3600)} hours`;
  return `about ${Math.round(s / 86400)} days`;
}

export default function Live() {
  const live = ROWS.filter((r) => r.state === "live").sort(
    (a, b) => a.migration_block - b.migration_block,
  );

  return (
    <main className="bg-paper-warm grain min-h-screen px-6 pb-28 pt-32 sm:px-10">
      <div className="mx-auto max-w-5xl">
        <p className="eyebrow mb-6">Open now · Robinhood Chain</p>
        <h1 className="display max-w-[17ch] text-[clamp(2.2rem,5vw,3.6rem)]">
          {live.length === 0
            ? "No auction is open right now."
            : `${live.length} auction${live.length === 1 ? " is" : "s are"} still open.`}
        </h1>
        <p className="mt-7 max-w-[60ch] text-ink-soft">
          {live.length === 0
            ? "Every recorded auction has passed its migration block. When a new one is created it is read and judged here before it closes."
            : "These have not reached their migration block, so the parameters below still govern where the money goes. This is the only page on this site about a decision you can still make."}
        </p>

        {live.length > 0 && (
          <ul className="mt-16 grid gap-px border border-hairline bg-hairline sm:grid-cols-2">
            {live.map((r) => (
              <li key={r.ini} className="bg-paper-raised">
                <Link href={`/launch/${r.ini}`} className="block p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <span className="data block truncate text-[1.15rem]">
                        {safeSymbol(r.sym, 18)}
                      </span>
                      <span className="data mt-1 block text-[11px] text-ink-soft">
                        {shortAddr(r.token)}
                      </span>
                    </div>
                    <span
                      className="data shrink-0 border px-2.5 py-1 text-[11px] tracking-[0.12em]"
                      style={{
                        color: CEILING_TONE[r.ceiling],
                        borderColor: CEILING_TONE[r.ceiling],
                      }}
                    >
                      {r.ceiling}
                    </span>
                  </div>

                  <dl className="mt-5 grid grid-cols-2 gap-x-5 gap-y-3">
                    {[
                      [
                        "priced in",
                        `${safeSymbol(r.cur_sym)}${r.cur_official ? " · official" : ""}`,
                      ],
                      ["LP reserve", pct(r.lp_ratio)],
                      [
                        "recipient",
                        r.rec_code > 0
                          ? "contract"
                          : r.rec_nonce === 0
                            ? "fresh EOA"
                            : "EOA",
                      ],
                      ["migrates in", remaining(r.migration_block - FEED.head)],
                    ].map(([k, v]) => (
                      <div key={k}>
                        <dt className="eyebrow !text-[10px]">{k}</dt>
                        <dd className="data mt-1 text-[13px]">{v}</dd>
                      </div>
                    ))}
                  </dl>

                  {r.findings.length > 0 && (
                    <p className="mt-5 border-t border-hairline pt-4 text-[13.5px] text-ink-soft">
                      {r.findings[0].d}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}

        <p className="data mt-14 max-w-[64ch] text-[11px] leading-relaxed text-ink-soft">
          Read at block {FEED.head.toLocaleString("en-US")}. Times are rough
          conversions from block distance, not promises. A verdict describes
          parameters, not intent, and is not advice about what to do with money.
        </p>
      </div>
    </main>
  );
}
