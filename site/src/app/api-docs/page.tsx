import type { Metadata } from "next";
import ApiTerminal from "@/components/ApiTerminal";
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

      {/* ── The paid lane ─────────────────────────────────────────────── */}
      <section className="bg-slate-glow grain px-6 py-24 sm:px-10">
        <div className="mx-auto max-w-4xl">
          <p className="eyebrow mb-6 !text-[#a2937c]">x402 · the paid lane</p>
          <h2 className="display max-w-[20ch] text-[clamp(1.9rem,4vw,3rem)] text-[#efe8da]">
            The record is a snapshot. This lane reads the chain now.
          </h2>
          <p className="mt-6 max-w-[58ch] text-[15px] text-[#a99a84]">
            The free files above are rebuilt every few minutes; a bidder
            deciding inside that window is deciding on old news. This endpoint
            answers at the current block — has the auction cleared, how much
            sold, how much raised, how many blocks remain — and never serves a
            cached answer. Payment is a USDG transfer on Robinhood Chain
            itself: no account, no API key, no card. The transaction is the
            receipt.
          </p>

          <div className="mt-10 grid gap-2 border-t border-[#33291d]">
            <div className="grid gap-2 border-b border-[#33291d] py-5 md:grid-cols-[22rem_1fr] md:gap-8">
              <span className="data text-[13px] text-brass-bright">
                /api/x402/watch/{"{auction}"}
              </span>
              <span className="text-[15px] text-[#a99a84]">
                Live auction state at the block your request lands on. 0.5
                USDG buys a 7-day pass — the 402 response below is the
                always-current price sheet.
              </span>
            </div>
          </div>

          <p className="eyebrow mb-6 mt-14 !text-[#a2937c]">How to pay</p>
          <div className="grid gap-x-10 gap-y-8 md:grid-cols-2">
            {[
              [
                "01",
                "Ask for the price",
                "Call the endpoint with no payment header. The 402 answer names the asset, amount and receiving address — never trust a doc page over the challenge itself.",
              ],
              [
                "02",
                "Pay on-chain, yourself",
                "Send 0.5 USDG to the payTo address on Robinhood Chain (4663), from any wallet whose key you hold. There is nothing of ours to approve and no contract of ours to call.",
              ],
              [
                "03",
                "Sign your receipt",
                "Paste your tx hash into the panel below and press sign with wallet — your wallet shows the text gavel-pass:<hash> and signs it, nothing more. cast wallet sign works too. The signature never goes on-chain.",
              ],
              [
                "04",
                "Retry with the header",
                "X-PAYMENT: <tx hash>.<signature> — that is the whole pass. It lasts 7 days from the block your payment landed in, on any request, with no account behind it.",
              ],
            ].map(([n, head, body]) => (
              <div key={n}>
                <div className="clause">{n}</div>
                <hr className="my-3 border-0" style={{ height: 1, background: "#33291d" }} />
                <h3 className="display text-[1.2rem] text-[#efe8da]">{head}</h3>
                <p className="mt-2 text-[14px] text-[#a99a84]">{body}</p>
              </div>
            ))}
          </div>

          <p className="eyebrow mb-4 mt-14 !text-[#a2937c]">Try it, against production</p>
          <ApiTerminal
            defaultAuction={(ROWS.find((r) => r.state === "live") ?? SAMPLE).ini}
          />
          <p className="mt-4 max-w-[58ch] text-[13px] text-[#7d7263]">
            Two things worth knowing before you pay: the server can verify
            payments but cannot spend them — there is no key on it — and
            signature recovery assumes the paying wallet is an EOA, so a
            smart-contract wallet (ERC-1271) cannot buy a pass yet.
          </p>
        </div>
      </section>

      <section className="bg-slate-glow-deep grain px-6 py-24 sm:px-10">
        <div className="mx-auto max-w-4xl">
          <p className="eyebrow mb-8 !text-[#a2937c]">Honest limits</p>
          <dl className="border-t border-[#33291d]">
            {[
              [
                "The free files are a snapshot, not a stream",
                `They are rebuilt from chain state, not served live. The current build was read at block ${FEED.head.toLocaleString("en-US")}; anything newer is not in them yet. The paid lane above is the exception — it reads the chain at request time.`,
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
