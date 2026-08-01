import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Copyable from "@/components/Copyable";
import {
  CEILING_TONE,
  ROWS,
  actionLink,
  STATE_LABEL,
  STATE_TONE,
  pct,
  safeSymbol,
  shortAddr,
} from "@/lib/feed";

export function generateStaticParams() {
  return ROWS.map((r) => ({ ini: r.ini }));
}

function find(ini: string) {
  return ROWS.find((r) => r.ini.toLowerCase() === ini.toLowerCase());
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ ini: string }>;
}): Promise<Metadata> {
  const { ini } = await params;
  const row = find(ini);
  if (!row) return { title: "Launch — GAVEL" };
  const sym = safeSymbol(row.sym);
  return {
    title: `${sym} — GAVEL`,
    description: `Launch auction ${sym} priced in ${safeSymbol(row.cur_sym)} on Robinhood Chain. Deterministic ceiling: ${row.ceiling}.`,
  };
}

const SEV_TONE: Record<string, string> = {
  PASS: "var(--pass)",
  FLAG: "var(--flag)",
  FAIL: "var(--fail)",
};

export default async function LaunchPage({
  params,
}: {
  params: Promise<{ ini: string }>;
}) {
  const { ini } = await params;
  const row = find(ini);
  if (!row) notFound();

  const action = actionLink(row);

  const facts: [string, React.ReactNode][] = [
    [
      "token",
      <>
        {safeSymbol(row.sym)} ·{" "}
        <Copyable value={row.token} label={shortAddr(row.token)} />
      </>,
    ],
    [
      "priced in",
      `${safeSymbol(row.cur_sym)}${row.cur_official ? " · official stock token" : ""}`,
    ],
    [
      "recipient",
      <>
        <Copyable value={row.recipient} label={shortAddr(row.recipient)} /> ·{" "}
        {row.rec_code > 0
          ? "contract"
          : row.rec_nonce === 0
            ? "fresh EOA, no history"
            : `EOA, ${row.rec_nonce} prior transactions`}
      </>,
    ],
    ["LP reserve", `${pct(row.lp_ratio)} of supply`],
    [
      "pool",
      `fee ${(row.fee / 10000).toFixed(2)}% · ${
        row.hook === "0x0000000000000000000000000000000000000000"
          ? "no hook"
          : `hook ${shortAddr(row.hook)}`
      }`,
    ],
    ["migration block", row.migration_block.toLocaleString("en-US")],
    ["created at block", row.block.toLocaleString("en-US")],
  ];

  return (
    <main className="bg-paper-warm grain min-h-screen px-6 pb-28 pt-32 sm:px-10">
      <div className="mx-auto max-w-4xl">
        <Link
          href="/launches"
          className="data text-[11px] tracking-[0.14em] text-ink-soft transition-colors hover:text-brass"
        >
          ← THE RECORD
        </Link>

        <div className="mt-8 flex flex-wrap items-start justify-between gap-6">
          <div>
            <p className="eyebrow mb-3">Launch auction</p>
            <h1 className="display text-[clamp(2.4rem,6vw,4rem)]">
              {safeSymbol(row.sym, 22)}
            </h1>
            <p className="data mt-3 flex items-center gap-2.5 text-[13px] text-ink-soft">
              <span
                aria-hidden
                className="block h-[12px] w-[3px]"
                style={{ background: STATE_TONE[row.state] }}
              />
              {STATE_LABEL[row.state]}
            </p>
          </div>
          <div className="text-right">
            <p className="eyebrow mb-3">Deterministic ceiling</p>
            <span
              className="data inline-block border px-6 py-3 text-[1.6rem] tracking-[0.14em]"
              style={{
                color: CEILING_TONE[row.ceiling],
                borderColor: CEILING_TONE[row.ceiling],
              }}
            >
              {row.ceiling}
            </span>
          </div>
        </div>

        {action && (
          <a
            href={action.href}
            target="_blank"
            rel="noreferrer"
            className="data mt-10 inline-flex items-center gap-2 border px-5 py-2.5 text-[12px] tracking-[0.12em] transition-colors"
            style={{ borderColor: "var(--brass)", color: "var(--brass)" }}
          >
            {action.label.toUpperCase()} ↗
          </a>
        )}

        <dl className="mt-16 border-t border-hairline">
          {facts.map(([k, v]) => (
            <div
              key={k}
              className="grid gap-1 border-b border-hairline py-5 sm:grid-cols-[13rem_1fr] sm:gap-8"
            >
              <dt className="data text-[12px] tracking-[0.06em] text-brass">
                {k}
              </dt>
              <dd className="data text-[14px]">{v}</dd>
            </div>
          ))}
        </dl>

        <section className="mt-16">
          <p className="eyebrow mb-6">Findings</p>
          {row.findings.length === 0 ? (
            <p className="text-ink-soft">
              No deterministic check raised anything on this launch. That is
              not a recommendation — it means the parameters carry none of the
              shapes these checks look for.
            </p>
          ) : (
            <ul className="border-t border-hairline">
              {row.findings.map((f) => (
                <li
                  key={f.k}
                  className="grid gap-2 border-b border-hairline py-5 sm:grid-cols-[7rem_1fr] sm:gap-6"
                >
                  <span
                    className="data h-fit w-fit border px-2 py-0.5 text-[10px] tracking-[0.14em]"
                    style={{ color: SEV_TONE[f.s], borderColor: SEV_TONE[f.s] }}
                  >
                    {f.s}
                  </span>
                  <span className="text-[15px] text-ink-soft">{f.d}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="mt-16 border-t border-hairline pt-8">
          <p className="eyebrow mb-5">Verify this yourself</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["creation transaction", row.tx],
              ["auction contract", row.ini],
              ["token contract", row.token],
              ["recipient address", row.recipient],
            ].map(([label, value]) => (
              <a
                key={label}
                href={`https://robinhoodchain.blockscout.com/${
                  label === "creation transaction" ? "tx" : "address"
                }/${value}`}
                target="_blank"
                rel="noreferrer"
                className="group block border border-hairline p-4 transition-colors hover:border-brass"
              >
                <span className="eyebrow">{label}</span>
                <span className="data mt-2 block text-[13px] transition-colors group-hover:text-brass">
                  {shortAddr(value)} ↗
                </span>
              </a>
            ))}
          </div>
        </section>

        <p className="data mt-14 max-w-[62ch] text-[11px] leading-relaxed text-ink-soft">
          The ceiling is what the deterministic checks allow. A judged verdict
          can sit at it or below it, never above. This page describes
          parameters, not intent, and is not advice about what to do with
          money.
        </p>
      </div>
    </main>
  );
}
