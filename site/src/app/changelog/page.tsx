import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Changelog — GAVEL",
  description:
    "What changed in the checks, and where GAVEL was wrong. A product that judges other people's honesty has to publish its own corrections.",
};

type Entry = {
  date: string;
  kind: "correction" | "check" | "coverage";
  head: string;
  body: string;
};

/* Corrections are listed with the same weight as features, deliberately.
   A verdict layer that never publishes its own mistakes is asking for a
   trust it has not earned. */
const ENTRIES: Entry[] = [
  {
    date: "2026-08-01",
    kind: "correction",
    head: "The record blamed neglect for something nobody was neglecting",
    body: "This site said that most auctions never became pools because nobody made the permissionless call to migrate them. That was an inference, and it was wrong. The chain emits no event for an auction that draws no bids — it simply sits past its migration block, which looks identical to one that cleared and was left alone. Reading each initializer directly settles it: they revert until a clearing price exists. Of 510 auctions, 384 never cleared at all, and every single auction that did clear was migrated. Not one was left sitting. The record now names the two states separately, because they are two different stories about the same silence.",
  },
  {
    date: "2026-08-01",
    kind: "correction",
    head: "The verdict said FLAG about almost everything, which is the same as saying nothing",
    body: "Under the first calibration 87% of the record sat below PASS, and the reason was a single check: paying an ordinary wallet was treated as a warning, when 85% of launches do exactly that. A signal that fires on five launches in six is not a signal. Findings now carry an INFO severity that is published but moves nothing, warnings are reserved for what is actually unusual — a recipient wallet with almost no history, a raise that routes less than half of itself to liquidity — and FAIL for what is structural, like a schedule that sends the money past liquidity entirely. Measured across the whole record of 462 launches the split is now 380 PASS, 72 FLAG and 10 FAIL. A verdict layer should be quiet like a smoke alarm, not loud like a car alarm.",
  },
  {
    date: "2026-08-01",
    kind: "correction",
    head: "The header showed a live block number over a snapshot",
    body: "The chip in the header reported the chain's current height, which read as a promise that the record was keeping pace with it. It was not: these pages are rebuilt from a snapshot, and that snapshot can be an hour or more behind. The chip now reports the block the data was actually read at and how far behind the chain that leaves it, and turns amber once the gap is wide enough to matter.",
  },
  {
    date: "2026-08-01",
    kind: "correction",
    head: "A genuine stock token was being called a likely impostor",
    body: "Currency authenticity was inferred from the token's name, so an auction priced in a real Robinhood stock token could be labelled a likely impostor purely because nothing verified the claim. The official issuer registry for chain 4663 is now consulted as fact: a registered address is verified, a name that claims the official pattern from an unregistered address is an impostor, and neither can be moved by the judge. Where the registry cannot be read at all, the answer is unknown — an unreachable registry is not evidence of forgery.",
  },
  {
    date: "2026-08-01",
    kind: "coverage",
    head: "The archive now covers every launch, not the ones we happened to see",
    body: "Server-side topic filtering meant the watcher only ever received the four event types it already knew about, so anything the protocol added would have been invisible while the cursor advanced past it. Filtering now happens after the fact: unknown events are archived as unknown rather than silently excluded. Rebuilding revealed 940 events that had been dropped, all of them belonging to four lifecycle events that now have decoders.",
  },
  {
    date: "2026-08-01",
    kind: "check",
    head: "The judge can no longer author anything you read",
    body: "An earlier design let the model write the headline and reasons on a verdict. An adversarial review showed that a token name carrying an injection could steer that copy — the verdict stayed correct while the sentence beside it reassured the reader. The model now returns only a verdict, a subset of our own finding keys, and labels from a closed list. Every published sentence is ours.",
  },
  {
    date: "2026-07-31",
    kind: "check",
    head: "Assessment labels are bounded by the facts",
    body: "The classification labels shown next to a verdict were taken from the judge without reconciliation, so a steered model could stamp 'verified official' on an unregistered currency or 'established' on a wallet with no history. Labels the facts decide are now replaced by the facts, labels the facts merely bound are coerced into the allowed set, and any disagreement with the chain is recorded and raises the manipulation flag.",
  },
];

const KIND_LABEL: Record<Entry["kind"], string> = {
  correction: "correction",
  check: "checks",
  coverage: "coverage",
};

const KIND_TONE: Record<Entry["kind"], string> = {
  correction: "var(--fail)",
  check: "var(--brass)",
  coverage: "var(--ink-soft)",
};

export default function Changelog() {
  const corrections = ENTRIES.filter((e) => e.kind === "correction").length;

  return (
    <main className="bg-paper-warm grain min-h-screen px-6 pb-28 pt-32 sm:px-10">
      <div className="mx-auto max-w-4xl">
        <p className="eyebrow mb-6">Changelog</p>
        <h1 className="display max-w-[19ch] text-[clamp(2.2rem,5vw,3.6rem)]">
          Where this was wrong, and when it changed.
        </h1>
        <p className="mt-7 max-w-[60ch] text-ink-soft">
          A product that judges how honestly other people configure their
          launches has no standing unless it publishes its own mistakes with
          the same prominence. Corrections are listed here beside features,
          not below them. {corrections} so far.
        </p>

        <ol className="mt-16 border-t border-hairline">
          {ENTRIES.map((e) => (
            <li
              key={e.head}
              className="grid gap-3 border-b border-hairline py-8 md:grid-cols-[11rem_1fr] md:gap-10"
            >
              <div>
                <time className="data block text-[12px] text-ink-soft">
                  {e.date}
                </time>
                <span
                  className="data mt-2 inline-block border px-2 py-0.5 text-[10px] tracking-[0.14em]"
                  style={{ color: KIND_TONE[e.kind], borderColor: KIND_TONE[e.kind] }}
                >
                  {KIND_LABEL[e.kind].toUpperCase()}
                </span>
              </div>
              <div>
                <h2 className="display text-[1.45rem]">{e.head}</h2>
                <p className="mt-3 text-[15.5px] text-ink-soft">{e.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="data mt-14 max-w-[64ch] text-[11px] leading-relaxed text-ink-soft">
          Every entry here corresponds to a commit in the public repository,
          and every correction has a regression test so the same mistake
          cannot return quietly.
        </p>
      </div>
    </main>
  );
}
