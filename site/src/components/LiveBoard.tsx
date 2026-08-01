"use client";

/**
 * The live board.
 *
 * The rows come from the build; the truth about whether they are still
 * open comes from the chain, re-read every twelve seconds in the reader's
 * own browser. A launch created since the build is announced separately
 * and explicitly as unread — this component reads the chain, it does not
 * run the checks, and pretending otherwise would be the exact dishonesty
 * the rest of the site exists to avoid.
 */

import Link from "next/link";
import {
  CEILING_TONE,
  LaunchRow,
  actionLink,
  rankFindings,
  pct,
  safeSymbol,
  shortAddr,
} from "@/lib/feed";
import { useLiveNow } from "@/components/LiveNow";

/* Robinhood Chain targets sub-second blocks. Used only to phrase a block
   distance in human terms, and labelled as rough wherever it is shown. */
const SECONDS_PER_BLOCK = 0.25;

function remaining(blocks: number) {
  if (blocks <= 0) return "any moment";
  const s = blocks * SECONDS_PER_BLOCK;
  if (s < 90) return "under two minutes";
  if (s < 5400) return `about ${Math.round(s / 60)} minutes`;
  if (s < 172800) return `about ${Math.round(s / 3600)} hours`;
  return `about ${Math.round(s / 86400)} days`;
}

export default function LiveBoard({
  rows,
  builtAt,
}: {
  rows: LaunchRow[];
  builtAt: number;
}) {
  const { head, stillOpen, fresh, error } = useLiveNow(rows);

  const open = rows
    .filter((r) => stillOpen.has(r.ini.toLowerCase()))
    .sort((a, b) => a.migration_block - b.migration_block);
  const closedSinceBuild = rows.length - open.length;
  const at = head ?? builtAt;

  return (
    <main className="bg-paper-warm grain min-h-screen px-6 pb-28 pt-32 sm:px-10">
      <div className="mx-auto max-w-5xl">
        <p className="eyebrow mb-6">Open now · Robinhood Chain</p>
        <h1 className="display max-w-[17ch] text-[clamp(2.2rem,5vw,3.6rem)]">
          {open.length === 0
            ? "No auction is open right now."
            : `${open.length} auction${open.length === 1 ? " is" : "s are"} still open.`}
        </h1>
        <p className="mt-7 max-w-[60ch] text-ink-soft">
          {open.length === 0
            ? "Every recorded auction has passed its migration block. When a new one is created it is read and judged here before it closes."
            : "These have not reached their migration block, so the parameters below still govern where the money goes. This is the only page on this site about a decision you can still make."}
        </p>

        <p
          className="data mt-6 inline-flex items-center gap-2 text-[11px] tracking-[0.12em]"
          style={{ color: error ? "var(--fail)" : "var(--ink-soft)" }}
        >
          <span
            aria-hidden
            className="block h-[6px] w-[6px] rounded-full"
            style={{
              background: error ? "var(--fail)" : "var(--pass)",
              opacity: head === null && !error ? 0.4 : 1,
            }}
          />
          {error
            ? "CHAIN UNREACHABLE — SHOWING THE LAST BUILD"
            : head === null
              ? "READING THE CHAIN…"
              : "OPEN OR CLOSED IS RE-READ FROM THE CHAIN, NOT FROM THE BUILD"}
        </p>

        {closedSinceBuild > 0 && !error && (
          <p className="data mt-3 text-[11px] text-ink-soft">
            {closedSinceBuild} auction{closedSinceBuild === 1 ? "" : "s"} in
            this build closed since it was cut and{" "}
            {closedSinceBuild === 1 ? "is" : "are"} no longer shown.
          </p>
        )}

        {fresh.length > 0 && (
          <div className="mt-10 border border-brass/40 bg-[rgba(154,116,32,0.05)] p-5">
            <p className="eyebrow !text-brass">
              {fresh.length} auction{fresh.length === 1 ? "" : "s"} opened since
              this build — not yet read
            </p>
            <p className="mt-3 max-w-[62ch] text-[14.5px] text-ink-soft">
              These exist on chain but the checks have not run against them,
              so GAVEL has nothing to say about their parameters yet. They are
              listed here rather than hidden, because a reader deciding right
              now should know they exist.
            </p>
            <ul className="mt-4 flex flex-wrap gap-2">
              {fresh.map((f) => (
                <a
                  key={f.ini}
                  href={`https://app.uniswap.org/explore/auctions/robinhood/${f.ini}`}
                  target="_blank"
                  rel="noreferrer"
                  className="data border border-hairline px-3 py-1.5 text-[11px] transition-colors hover:border-brass hover:text-brass"
                >
                  {shortAddr(f.token)} · closes in{" "}
                  {remaining(f.migrationBlock - at)} ↗
                </a>
              ))}
            </ul>
          </div>
        )}

        {open.length > 0 && (
          <ul className="mt-16 grid gap-px border border-hairline bg-hairline sm:grid-cols-2">
            {open.map((r) => (
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
                      ["migrates in", remaining(r.migration_block - at)],
                    ].map(([k, v]) => (
                      <div key={k}>
                        <dt className="eyebrow !text-[10px]">{k}</dt>
                        <dd className="data mt-1 text-[13px]">{v}</dd>
                      </div>
                    ))}
                  </dl>

                  {r.findings.length > 0 && (
                    <p className="mt-5 border-t border-hairline pt-4 text-[13.5px] text-ink-soft">
                      {rankFindings(r.findings)[0].d}
                    </p>
                  )}
                </Link>
                {actionLink(r) && (
                  <a
                    href={actionLink(r)!.href}
                    target="_blank"
                    rel="noreferrer"
                    className="data mx-6 mb-6 inline-block text-[11px] tracking-[0.12em] transition-colors hover:text-brass"
                    style={{ color: "var(--brass)" }}
                  >
                    OPEN AUCTION ON UNISWAP ↗
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}

        <p className="data mt-14 max-w-[64ch] text-[11px] leading-relaxed text-ink-soft">
          Parameters and verdicts come from the build at block{" "}
          {builtAt.toLocaleString("en-US")}; whether an auction is still open
          is re-read from the chain every twelve seconds. Times are rough
          conversions from block distance, not promises. A verdict describes
          parameters, not intent, and is not advice about what to do with
          money.
        </p>
      </div>
    </main>
  );
}
