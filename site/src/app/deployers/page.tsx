import type { Metadata } from "next";
import Link from "next/link";
import raw from "@/app/deployers.json";
import { pct, safeSymbol, shortAddr } from "@/lib/feed";

export const metadata: Metadata = {
  title: "Deployers — GAVEL",
  description:
    "Every address that has created a launch auction on Robinhood Chain, and what became of the launches it created.",
};

type Deployer = {
  addr: string;
  n: number;
  pool: number;
  failed: number;
  live: number;
  silent: number;
  median_lp: number | null;
  is_contract: boolean;
  first_block: number;
  last_block: number;
  tokens: { sym: string | null; ini: string; state: string; ceiling: string }[];
};

const DATA = raw as { head: number; deployers: Deployer[] };
const REPEAT = DATA.deployers.filter((d) => d.n > 1);

export default function Deployers() {
  const total = DATA.deployers.length;
  const mostActive = REPEAT.slice(0, 40);

  return (
    <main className="bg-paper-warm grain min-h-screen px-6 pb-28 pt-32 sm:px-10">
      <div className="mx-auto max-w-6xl">
        <p className="eyebrow mb-6">Provenance · Robinhood Chain</p>
        <h1 className="display max-w-[20ch] text-[clamp(2.2rem,5vw,3.6rem)]">
          Who launched it, and what happened last time.
        </h1>
        <p className="mt-7 max-w-[62ch] text-ink-soft">
          GAVEL cannot tell you a deployer is honest — nobody can read
          intent from an address. What it can do is show the record: how many
          auctions this address has created, how many became pools, and how
          much of each raise was set aside for liquidity. A first launch has
          no history, and that is itself worth knowing.
        </p>

        <dl className="mt-12 grid gap-px border border-hairline bg-hairline sm:grid-cols-3">
          {[
            ["Distinct deployers", total],
            ["Launched more than once", REPEAT.length],
            ["Most launches by one address", DATA.deployers[0]?.n ?? 0],
          ].map(([label, value]) => (
            <div key={String(label)} className="bg-paper-raised p-5">
              <dd className="data text-[1.9rem] leading-none">
                {Number(value).toLocaleString("en-US")}
              </dd>
              <dt className="eyebrow mt-2.5">{String(label)}</dt>
            </div>
          ))}
        </dl>

        <p className="eyebrow mt-16 mb-5">
          Repeat deployers, most active first
        </p>

        <ul className="border-t border-hairline">
          {mostActive.map((d) => {
            const poolRate = d.n ? d.pool / d.n : 0;
            return (
              <li key={d.addr} className="border-b border-hairline py-6">
                <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
                  <a
                    href={`https://robinhoodchain.blockscout.com/address/${d.addr}`}
                    target="_blank"
                    rel="noreferrer"
                    className="data text-[14px] transition-colors hover:text-brass"
                  >
                    {shortAddr(d.addr)} ↗
                  </a>
                  <span className="data text-[11px] text-ink-soft">
                    {d.is_contract ? "contract" : "externally owned account"}
                  </span>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-5">
                  {[
                    ["launches", String(d.n)],
                    ["became pools", `${d.pool} · ${Math.round(poolRate * 100)}%`],
                    ["never migrated", String(d.silent)],
                    ["migration failed", String(d.failed)],
                    ["median LP reserve", pct(d.median_lp)],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <span className="eyebrow !text-[10px]">{k}</span>
                      <span
                        className="data mt-1 block text-[13.5px]"
                        style={
                          k === "migration failed" && d.failed > 0
                            ? { color: "var(--fail)" }
                            : k === "became pools" && d.pool > 0
                              ? { color: "var(--brass)" }
                              : undefined
                        }
                      >
                        {v}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="mt-4 flex flex-wrap gap-x-2 gap-y-1.5">
                  {d.tokens.map((t) => (
                    <Link
                      key={t.ini}
                      href={`/launch/${t.ini}`}
                      className="data border border-hairline px-2 py-0.5 text-[11px] text-ink-soft transition-colors hover:border-brass hover:text-brass"
                    >
                      {safeSymbol(t.sym, 12)}
                    </Link>
                  ))}
                </div>
              </li>
            );
          })}
        </ul>

        <p className="data mt-14 max-w-[64ch] text-[11px] leading-relaxed text-ink-soft">
          Read at block {DATA.head.toLocaleString("en-US")}. Showing the{" "}
          {mostActive.length} most active of {REPEAT.length} addresses that
          launched more than once. A record is not a character reference: an
          address with a good history can still configure its next auction
          badly, which is why every launch is judged on its own parameters.
        </p>
      </div>
    </main>
  );
}
