"use client";

/**
 * A live request panel for the paid endpoint — the docs page's proof that
 * the thing exists. Docs that only describe an API ask to be believed;
 * a panel that hits production in front of the reader does not.
 *
 * It fires real requests at the real endpoint. Without a payment header
 * the answer is the genuine 402 price sheet, which doubles as the always-
 * current source of truth for price and pay-to address — the prose around
 * this panel can go stale, the challenge cannot.
 */

import { useEffect, useState } from "react";
import Copyable from "./Copyable";

const API_BASE = "https://www.gavelscan.xyz";

type Result = { status: number | null; body: string; ms: number };

type PriceSheet = {
  payTo: string;
  amountUsdg: number;
  assetSymbol: string;
  passDays: number | null;
};

/**
 * The payment strip is read from the live 402 challenge, never hardcoded:
 * the page must stay unable to disagree with the endpoint about price or
 * address. Any well-formed address earns the challenge before the chain
 * is touched, so this probe costs one round trip and zero RPC calls.
 */
function usePriceSheet(): PriceSheet | null {
  const [sheet, setSheet] = useState<PriceSheet | null>(null);
  useEffect(() => {
    let alive = true;
    fetch(`${API_BASE}/api/x402/watch/0x${"aa".repeat(20)}`, { cache: "no-store" })
      .then((r) => (r.status === 402 ? r.json() : null))
      .then((d) => {
        const a = d?.accepts?.[0];
        if (alive && a?.payTo && a?.maxAmountRequired) {
          const days = /(\d+)-day/.exec(a.description ?? "");
          setSheet({
            payTo: a.payTo,
            amountUsdg: Number(a.maxAmountRequired) / 1e6,
            assetSymbol: a.assetSymbol ?? "USDG",
            passDays: days ? Number(days[1]) : null,
          });
        }
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);
  return sheet;
}

function statusTone(status: number | null): string {
  if (status === null) return "var(--fail)";
  if (status === 200) return "var(--pass)";
  if (status === 402) return "var(--brass-bright)";
  return "var(--fail)";
}

function statusWord(status: number | null): string {
  if (status === null) return "UNREACHABLE";
  if (status === 200) return "200 OK";
  if (status === 402) return "402 PAYMENT REQUIRED";
  return `HTTP ${status}`;
}

export default function ApiTerminal({ defaultAuction }: { defaultAuction: string }) {
  const sheet = usePriceSheet();
  const [auction, setAuction] = useState(defaultAuction);
  const [payment, setPayment] = useState("");
  const [out, setOut] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);

  const addr = auction.trim().toLowerCase();
  const curl =
    `curl ${payment.trim() ? `-H "X-PAYMENT: ${payment.trim().slice(0, 18)}…" ` : ""}` +
    `${API_BASE}/api/x402/watch/${addr || "{auction}"}`;

  async function run() {
    setBusy(true);
    const t0 = performance.now();
    try {
      const res = await fetch(`${API_BASE}/api/x402/watch/${addr}`, {
        headers: payment.trim() ? { "x-payment": payment.trim() } : undefined,
        cache: "no-store",
      });
      const text = await res.text();
      let body = text;
      try {
        body = JSON.stringify(JSON.parse(text), null, 2);
      } catch {
        /* non-JSON error page: show it as-is */
      }
      setOut({ status: res.status, body, ms: performance.now() - t0 });
    } catch {
      setOut({
        status: null,
        body: "network error — the endpoint could not be reached from this browser",
        ms: performance.now() - t0,
      });
    } finally {
      setBusy(false);
    }
  }

  const inputCls =
    "data w-full border border-[#33291d] bg-[#100d09] px-4 py-3 text-[13px] " +
    "text-[#efe8da] placeholder:text-[#5d5344] focus:border-brass-bright focus:outline-none";

  return (
    <div className="border border-[#33291d] bg-[#120f0b]">
      <div className="flex items-center justify-between border-b border-[#33291d] px-5 py-3">
        <span className="data text-[11px] tracking-[0.2em] text-[#7d7263]">
          LIVE REQUEST · PRODUCTION
        </span>
        <span className="data text-[11px] text-[#7d7263]">GET /api/x402/watch</span>
      </div>

      <div className="grid gap-3 p-5">
        <label className="grid gap-1.5">
          <span className="data text-[11px] text-[#7d7263]">auction (initializer address)</span>
          <input
            className={inputCls}
            value={auction}
            onChange={(e) => setAuction(e.target.value)}
            spellCheck={false}
          />
        </label>
        {sheet && (
          <div className="grid gap-1.5 border border-[#33291d] bg-[#161209] px-4 py-3">
            <span className="data text-[11px] text-[#7d7263]">
              pay to — {sheet.amountUsdg} {sheet.assetSymbol} on Robinhood Chain
              {sheet.passDays ? ` · ${sheet.passDays}-day pass` : ""} · read live
              from the 402 challenge
            </span>
            <Copyable
              value={sheet.payTo}
              className="data justify-start break-all text-left text-[13px] text-brass-bright"
            />
          </div>
        )}

        <label className="grid gap-1.5">
          <span className="data text-[11px] text-[#7d7263]">
            X-PAYMENT — optional; leave empty to see the 402 price sheet
          </span>
          <input
            className={inputCls}
            value={payment}
            onChange={(e) => setPayment(e.target.value)}
            placeholder="0x<txhash>.0x<signature>"
            spellCheck={false}
          />
        </label>

        <div className="mt-1 flex flex-wrap items-center gap-4">
          <button
            onClick={run}
            disabled={busy || !/^0x[0-9a-f]{40}$/.test(addr)}
            className="data border border-brass-bright px-6 py-2.5 text-[13px] text-brass-bright transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-35"
          >
            {busy ? "reading the chain…" : "send request"}
          </button>
          <code className="data hidden min-w-0 flex-1 truncate text-[11.5px] text-[#5d5344] sm:block">
            {curl}
          </code>
        </div>
      </div>

      {out && (
        <div className="border-t border-[#33291d]">
          <div className="flex items-center gap-4 px-5 py-3">
            <span className="data text-[12px] font-bold" style={{ color: statusTone(out.status) }}>
              {statusWord(out.status)}
            </span>
            <span className="data text-[11px] text-[#5d5344]">{Math.round(out.ms)} ms</span>
          </div>
          <pre className="data max-h-96 overflow-auto border-t border-[#33291d] bg-[#0d0b08] p-5 text-[12px] leading-relaxed text-[#cfc6b4]">
            {out.body}
          </pre>
        </div>
      )}
    </div>
  );
}
