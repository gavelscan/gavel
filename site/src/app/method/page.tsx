import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Method — GAVEL",
  description:
    "How a GAVEL verdict is made: deterministic checks set a ceiling, a judge reasons below it, and the ceiling can never be raised.",
};

const CLAUSES = [
  {
    n: "01",
    head: "The chain is the only source",
    body: "Every figure is fetched from a Robinhood Chain RPC directly — logs, contract code, balances, storage reads. No indexer and no price API is treated as evidence. When a node cannot be reached, that is an error state, never an empty result: unknown is not the same as safe.",
  },
  {
    n: "02",
    head: "Deterministic checks set a ceiling",
    body: "The auction parameters are decoded and checked: the LP allocation schedule bracket by bracket, the position plan, the committed pool, the recipient's code and history, and the currency's identity against the issuer registry. Whatever those facts allow becomes the best verdict this launch can receive.",
  },
  {
    n: "03",
    head: "A judge reasons below the ceiling",
    body: "An agent takes the factsheet and classifies what a script cannot settle: whether a custom hook's economics look hostile, what the deployer's provenance suggests, how much of the picture is genuinely unresolved. It may lower a verdict. The code that applies its answer cannot raise one.",
  },
  {
    n: "04",
    head: "The verdict is published with its evidence",
    body: "Three states, no scores: PASS, FLAG, FAIL. Each verdict carries the findings it rests on and the transaction it came from, so a reader can disagree with the reasoning without having to trust the reader.",
  },
];

const GUARANTEES = [
  [
    "The ceiling can never be raised",
    "A hard failure caps the verdict at FAIL and a warning caps it at FLAG. This is enforced in code and tested exhaustively, so a model having a bad day — or one steered by a hostile token name — cannot talk a launch up.",
  ],
  [
    "The model writes none of the words you read",
    "It returns a verdict, a set of our own finding keys, and classification labels from a closed list. Every sentence on a card or a page is ours. There is no path for injected copy to reach a reader.",
  ],
  [
    "Claims of officialdom are checked, not believed",
    "A currency is an official Robinhood stock token only if its address is in the issuer's registry. A name that claims the pattern from an unregistered address is called an impostor — and only when the registry was actually readable.",
  ],
  [
    "GAVEL never touches funds",
    "No custody, no keys, no wallet connection anywhere in the system. If every GAVEL process stopped right now, no one's money would be affected, because there is no path from this software to money.",
  ],
];

export default function Method() {
  return (
    <main>
      <section className="bg-paper-warm grain px-6 pb-24 pt-32 sm:px-10">
        <div className="mx-auto max-w-6xl">
          <p className="eyebrow mb-6">Method</p>
          <h1 className="display max-w-[19ch] text-[clamp(2.2rem,5vw,3.6rem)]">
            A verdict is only worth what its procedure is worth.
          </h1>
          <p className="mt-7 max-w-[60ch] text-ink-soft">
            Uniswap&rsquo;s documentation warns that an auction can be
            configured with malicious parameters and tells every reader to
            validate them. This is how that validation runs here, in the order
            it runs — the order is the safety property.
          </p>

          <div className="mt-20 grid gap-x-12 gap-y-14 md:grid-cols-2">
            {CLAUSES.map((c) => (
              <div key={c.n}>
                <div className="clause">{c.n}</div>
                <hr className="hair my-4" />
                <h2 className="display text-[1.7rem]">{c.head}</h2>
                <p className="mt-3 text-[15.5px] text-ink-soft">{c.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div aria-hidden className="bridge-paper-to-dark grain" />

      <section className="bg-slate-glow grain px-6 py-24 sm:px-10 sm:py-32">
        <div className="mx-auto max-w-6xl">
          <p className="eyebrow mb-8 !text-[#a2937c]">What is guaranteed</p>
          <dl className="border-t border-[#33291d]">
            {GUARANTEES.map(([term, def]) => (
              <div
                key={term}
                className="grid gap-3 border-b border-[#33291d] py-7 md:grid-cols-[22rem_1fr] md:gap-10"
              >
                <dt className="display text-[1.35rem] text-[#efe8da]">
                  {term}
                </dt>
                <dd className="text-[15.5px] text-[#a99a84]">{def}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-16 flex flex-wrap items-center gap-5">
            <Link
              href="/launches"
              className="data border px-5 py-2.5 text-[12px] tracking-[0.12em] transition-colors"
              style={{ borderColor: "var(--brass)", color: "var(--brass)" }}
            >
              READ THE RECORD
            </Link>
            <a
              href="https://github.com/gavelscan/gavel"
              className="data text-[12px] text-[#a2937c] transition-colors hover:text-brass"
            >
              the checks, in full, on github
            </a>
          </div>

          <p className="data mt-16 max-w-[64ch] text-[11px] leading-relaxed text-[#7d7263]">
            What GAVEL cannot see: intent. It reads parameters and provenance.
            A launch that passes every check can still fail, and a flagged
            launch is not an accusation of fraud — it is a statement that
            something in the configuration deserves a second look before money
            moves.
          </p>
        </div>
      </section>
    </main>
  );
}
