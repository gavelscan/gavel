import Image from "next/image";
import LaunchField from "@/components/LaunchField";
import Reveal from "@/components/Reveal";
import launches from "./launches.json";

type Row = { s: "pool" | "failed" | "live" | "silent"; c: number };
const DATA = launches as Row[];
const count = (s: Row["s"]) => DATA.filter((d) => d.s === s).length;

const TOTAL = DATA.length;
const POOL = count("pool");
const FAILED = count("failed");
const LIVE = count("live");
const SILENT = count("silent");
const TOKEN_PAIRED = DATA.filter((d) => d.c === 1).length;

const LEGEND = [
  { key: "silent", label: "never migrated", n: SILENT, tone: "#6e737a" },
  { key: "pool", label: "became a pool", n: POOL, tone: "var(--brass)" },
  { key: "failed", label: "migration failed", n: FAILED, tone: "var(--fail)" },
  { key: "live", label: "still in auction", n: LIVE, tone: "#e8e4da" },
];

/* Numbered because this genuinely is an ordered procedure: the ceiling is
   computed before the judge is asked, and the clamp runs after it answers.
   The order is the safety property, so the reader needs it. */
const PROCEDURE = [
  {
    n: "01",
    head: "Read the parameters",
    body: "Deterministic checks decode the auction: where raised currency goes on every path, the LP allocation schedule, the committed pool, the recipient's history, and what the currency actually is.",
  },
  {
    n: "02",
    head: "Set the ceiling",
    body: "Those facts fix the best verdict a launch can receive. A hard failure caps it at FAIL, a warning at FLAG. Nothing downstream can lift it.",
  },
  {
    n: "03",
    head: "Judge what scripts cannot",
    body: "An agent reasons about hook behaviour, currency identity and deployer provenance, then classifies. It may lower the verdict below the ceiling. It can never raise it.",
  },
];

const READS: [string, string][] = [
  ["recipient", "Who receives the raised currency and the reserved LP tokens if migration fails."],
  ["allocation schedule", "How much of the raise is routed to liquidity, bracket by bracket, and how much exits."],
  ["committed pool", "The exact fee, tick spacing and hook the launch has bound itself to."],
  ["currency", "What the auction is priced in, and whether that asset is what its name claims."],
  ["position plan", "Whether the configured LP positions can actually be created at the discovered price."],
  ["migration window", "The block after which anyone may migrate, and whether it has passed unused."],
];

export default function Home() {
  return (
    <main>
      {/* ── Hero: the field is the thesis ──────────────────────────────── */}
      <LaunchField>
        {/* Scrim: the field must stay visible behind the headline without
            costing the headline its contrast. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "linear-gradient(100deg, rgba(14,17,19,.94) 0%, rgba(14,17,19,.82) 34%, rgba(14,17,19,.15) 62%, rgba(14,17,19,0) 100%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-40"
          style={{
            background:
              "linear-gradient(to top, rgba(14,17,19,.92), rgba(14,17,19,0))",
          }}
        />
        <div className="pointer-events-none absolute inset-0 flex flex-col justify-end gap-10 p-6 pb-6 sm:p-10">
          <div className="max-w-[46rem]">
            <p className="eyebrow mb-5 !text-brass">
              Robinhood Chain · Uniswap Liquidity Launcher
            </p>
            <h1 className="display text-[clamp(2.6rem,6.4vw,5.4rem)] text-[#f2efe7]">
              Every launch auction,
              <br />
              read before the
              <span className="italic text-brass"> money moves</span>.
            </h1>
          </div>

          {/* The legend is what turns the field from decoration into an
              instrument: every bar becomes readable. */}
          <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
            {LEGEND.map((l) => (
              <div key={l.key} className="flex items-center gap-2.5">
                <span
                  aria-hidden
                  style={{ background: l.tone }}
                  className="block h-[13px] w-[3px]"
                />
                <span className="data text-[11px] text-[#8f949b]">
                  <span className="text-[#e2ded4]">{l.n}</span> {l.label}
                </span>
              </div>
            ))}
            <span className="data ml-auto hidden text-[11px] text-[#5f656c] sm:block">
              one bar = one launch · scroll
            </span>
          </div>
        </div>
      </LaunchField>

      <div aria-hidden className="bridge-dark-to-paper grain" />

      {/* ── The finding ────────────────────────────────────────────────── */}
      <section className="bg-paper-warm grain px-6 py-24 sm:px-10 sm:py-32">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <p className="eyebrow mb-8">Archive · every launch to date</p>
          </Reveal>
          <Reveal delay={0.05}>
            <h2 className="display max-w-[22ch] text-[clamp(2rem,4.4vw,3.4rem)]">
              {TOTAL} launch auctions have run through the launcher.
              <span className="text-brass"> {POOL} became pools.</span>
            </h2>
          </Reveal>
          <Reveal delay={0.1}>
            <p className="mt-8 max-w-[58ch] text-ink-soft">
              Migration is permissionless: once the migration block passes,
              anyone can turn a finished auction into a live pool. For most
              launches here, nobody ever made that call. Another {FAILED}{" "}
              reached migration and failed, which returns the raised currency
              and the reserved LP tokens to an address the deployer chose in
              advance.
            </p>
          </Reveal>

          <div className="mt-16 grid gap-px border border-hairline bg-hairline sm:grid-cols-4">
            {[
              ["Archived events", "2,214"],
              ["Launch auctions", String(TOTAL)],
              ["Token-paired", String(TOKEN_PAIRED)],
              ["Migration failures", String(FAILED)],
            ].map(([label, value], i) => (
              <Reveal key={label} delay={i * 0.06} className="bg-paper">
                <div className="p-6">
                  <div className="data text-[clamp(1.8rem,3vw,2.6rem)] leading-none">
                    {value}
                  </div>
                  <div className="eyebrow mt-3">{label}</div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Procedure ──────────────────────────────────────────────────── */}
      <section className="bg-paper-sunk-warm grain px-6 py-24 sm:px-10 sm:py-32">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <p className="eyebrow mb-8">How a verdict is made</p>
          </Reveal>
          <div className="grid gap-x-10 gap-y-12 md:grid-cols-3">
            {PROCEDURE.map((p, i) => (
              <Reveal key={p.n} delay={i * 0.08}>
                <div className="clause">{p.n}</div>
                <hr className="hair my-4" />
                <h3 className="display text-[1.65rem]">{p.head}</h3>
                <p className="mt-3 text-[15.5px] text-ink-soft">{p.body}</p>
              </Reveal>
            ))}
          </div>
          <Reveal delay={0.3}>
            <div className="mt-16 flex flex-wrap items-center gap-3">
              {(
                [
                  ["PASS", "var(--pass)"],
                  ["FLAG", "var(--flag)"],
                  ["FAIL", "var(--fail)"],
                ] as [string, string][]
              ).map(([label, tone]) => (
                <span
                  key={label}
                  style={{ color: tone, borderColor: tone }}
                  className="data border px-4 py-1.5 text-[12px] tracking-[0.16em]"
                >
                  {label}
                </span>
              ))}
              <span className="data ml-2 text-[12px] text-ink-soft">
                three states. no scores, no percentages.
              </span>
            </div>
          </Reveal>
        </div>
      </section>

      <div aria-hidden className="bridge-paper-to-dark grain" />

      {/* ── What gets read ─────────────────────────────────────────────── */}
      <section className="bg-slate-glow grain px-6 py-24 sm:px-10 sm:py-32">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <p className="eyebrow mb-8 !text-[#8f949b]">What gets read</p>
          </Reveal>
          <Reveal delay={0.05}>
            <blockquote className="display max-w-[26ch] text-[clamp(1.7rem,3.4vw,2.6rem)] text-[#f2efe7]">
              Uniswap&rsquo;s own documentation calls it{" "}
              <span className="italic text-brass">
                &ldquo;trivially easy&rdquo;
              </span>{" "}
              to configure an auction with malicious parameters, and tells you
              to validate every one yourself.
            </blockquote>
          </Reveal>
          <Reveal delay={0.1}>
            <p className="mt-6 max-w-[54ch] text-[#9aa0a8]">
              That is the whole job. These are the fields a verdict is built
              from — all public, all readable before an auction closes.
            </p>
          </Reveal>

          <dl className="mt-16 border-t border-[#2a2e33]">
            {READS.map(([term, def], i) => (
              <Reveal key={term} delay={i * 0.04}>
                <div className="grid gap-2 border-b border-[#2a2e33] py-6 md:grid-cols-[16rem_1fr] md:gap-10">
                  <dt className="data text-[13px] tracking-[0.05em] text-brass">
                    {term}
                  </dt>
                  <dd className="text-[15.5px] text-[#9aa0a8]">{def}</dd>
                </div>
              </Reveal>
            ))}
          </dl>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer className="bg-slate-glow-deep grain px-6 py-20 sm:px-10">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <p className="display max-w-[18ch] text-[clamp(1.8rem,3.6vw,2.8rem)] text-[#f2efe7]">
              Read the gavel before you bid.
            </p>
          </Reveal>
          <div className="mt-14 flex flex-wrap items-center justify-between gap-6 border-t border-[#23272b] pt-8">
            <div className="flex items-center gap-3">
              <Image
                src="/brand/gavel-mark-tight.png"
                alt=""
                width={26}
                height={26}
              />
              <span className="data text-[11px] tracking-[0.2em] text-[#8f949b]">
                GAVELSCAN
              </span>
            </div>
            <nav className="flex gap-8">
              <a
                href="https://x.com/gavelscan"
                className="data text-[12px] text-[#8f949b] transition-colors hover:text-brass"
              >
                x.com/gavelscan
              </a>
              <a
                href="https://github.com/gavelscan/gavel"
                className="data text-[12px] text-[#8f949b] transition-colors hover:text-brass"
              >
                github
              </a>
            </nav>
          </div>
          <p className="data mt-8 max-w-[62ch] text-[11px] leading-relaxed text-[#5f656c]">
            GAVEL publishes an opinion about risk, not a guarantee of outcome. A
            verdict describes what a launch&rsquo;s parameters say. It is not
            advice about what to do with money.
          </p>
        </div>
      </footer>
    </main>
  );
}
