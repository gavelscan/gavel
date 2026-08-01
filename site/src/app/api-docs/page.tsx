import type { Metadata } from "next";
import { FEED, ROWS } from "@/lib/feed";

export const metadata: Metadata = {
  title: "API — GAVEL",
  description:
    "Read every launch auction, its deterministic findings and its verdict ceiling as JSON. Static, free, no key.",
};

const SAMPLE = ROWS.find((r) => r.cur_official) ?? ROWS[0];

const ENDPOINTS = [
  {
    path: "/v1/live.json",
    what: "Auctions that have not reached their migration block. The only endpoint about a decision that is still open.",
  },
  {
    path: "/v1/launches.json",
    what: `Every recorded auction — ${ROWS.length} of them — with findings and ceiling.`,
  },
  {
    path: "/v1/launch/{auction}.json",
    what: "One auction by its initializer address, lowercase.",
  },
  {
    path: "/v1/deployers.json",
    what: "Every address that has created an auction, with its record.",
  },
  {
    path: "/v1/deployer/{address}.json",
    what: "One deployer by address, lowercase, with its recent launches.",
  },
];

const FIELDS: [string, string][] = [
  ["ceiling", "PASS, FLAG or FAIL. The best verdict the deterministic checks allow. A judged verdict may sit at it or below it, never above."],
  ["findings[]", "Every check that fired, with its severity and the sentence GAVEL publishes for it. These strings are ours; nothing here is written by a model."],
  ["currency.official_stock_token", "True only when the address is in the Robinhood issuer registry. A matching name is not enough."],
  ["recipient", "Where raised currency and reserved LP tokens go if migration fails. is_contract and nonce are read from the chain at build time."],
  ["lp_reserve_ratio", "Share of token supply set aside for liquidity, as a fraction."],
  ["outcome", "pool, failed, live or silent — what has become of the auction so far."],
];

function Code({ children }: { children: string }) {
  return (
    <pre className="data overflow-x-auto border border-hairline bg-paper-raised p-5 text-[12.5px] leading-relaxed">
      {children}
    </pre>
  );
}

export default function ApiDocs() {
  const sample = {
    auction: SAMPLE.ini,
    tx: SAMPLE.tx,
    block: SAMPLE.block,
    token: { address: SAMPLE.token, symbol: SAMPLE.sym },
    currency: {
      address: SAMPLE.currency,
      symbol: SAMPLE.cur_sym,
      official_stock_token: SAMPLE.cur_official,
    },
    recipient: {
      address: SAMPLE.recipient,
      is_contract: SAMPLE.rec_code > 0,
      nonce: SAMPLE.rec_nonce,
    },
    lp_reserve_ratio: SAMPLE.lp_ratio,
    pool: { fee: SAMPLE.fee, hook: SAMPLE.hook },
    migration_block: SAMPLE.migration_block,
    outcome: SAMPLE.state,
    ceiling: SAMPLE.ceiling,
    findings: SAMPLE.findings.map((f) => ({
      check: f.k,
      severity: f.s,
      detail: f.d,
    })),
  };

  return (
    <main>
      <section className="bg-paper-warm grain px-6 pb-24 pt-32 sm:px-10">
        <div className="mx-auto max-w-4xl">
          <p className="eyebrow mb-6">API</p>
          <h1 className="display max-w-[18ch] text-[clamp(2.2rem,5vw,3.6rem)]">
            The record, as JSON.
          </h1>
          <p className="mt-7 max-w-[58ch] text-ink-soft">
            Nobody stops mid-auction to open a third-party website. If a
            verdict is going to be useful it has to reach the tool a reader is
            already in, so every page here is also a file a machine can read.
            Static JSON, no key, no rate limit, same data the site renders.
          </p>

          <Code>{`curl https://gavelscan.xyz/v1/live.json`}</Code>

          <p className="eyebrow mb-4 mt-16">Endpoints</p>
          <dl className="border-t border-hairline">
            {ENDPOINTS.map((e) => (
              <div
                key={e.path}
                className="grid gap-2 border-b border-hairline py-5 md:grid-cols-[22rem_1fr] md:gap-8"
              >
                <dt className="data text-[13px] text-brass">{e.path}</dt>
                <dd className="text-[15px] text-ink-soft">{e.what}</dd>
              </div>
            ))}
          </dl>

          <p className="eyebrow mb-4 mt-16">A launch, in full</p>
          <Code>{JSON.stringify(sample, null, 2)}</Code>

          <p className="eyebrow mb-4 mt-16">Fields worth explaining</p>
          <dl className="border-t border-hairline">
            {FIELDS.map(([k, v]) => (
              <div
                key={k}
                className="grid gap-2 border-b border-hairline py-5 md:grid-cols-[16rem_1fr] md:gap-8"
              >
                <dt className="data text-[13px] text-brass">{k}</dt>
                <dd className="text-[15px] text-ink-soft">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <div aria-hidden className="bridge-paper-to-dark grain" />

      <section className="bg-slate-glow grain px-6 py-24 sm:px-10">
        <div className="mx-auto max-w-4xl">
          <p className="eyebrow mb-8 !text-[#a2937c]">Honest limits</p>
          <dl className="border-t border-[#33291d]">
            {[
              [
                "It is a snapshot, not a stream",
                `These files are rebuilt from chain state, not served live. The current build was read at block ${FEED.head.toLocaleString("en-US")}. Anything created after that is not in here yet.`,
              ],
              [
                "The ceiling is deterministic; the judge is not published here yet",
                "Every file carries the checks and the ceiling. Judged classifications are being added once their calibration is settled — publishing an uncalibrated verdict would be worse than publishing none.",
              ],
              [
                "No key, and therefore no promises",
                "There is no account, no quota and no support commitment. If you build something that matters on it, pin a copy.",
              ],
            ].map(([term, def]) => (
              <div
                key={term}
                className="grid gap-3 border-b border-[#33291d] py-7 md:grid-cols-[22rem_1fr] md:gap-10"
              >
                <dt className="display text-[1.3rem] text-[#efe8da]">{term}</dt>
                <dd className="text-[15px] text-[#a99a84]">{def}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
    </main>
  );
}
