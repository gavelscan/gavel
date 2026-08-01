"use client";

/**
 * The header reads as the top of a document, not a marketing bar: a
 * hairline rule, monospaced labels, and a live block height on the right.
 *
 * The block number is the point. It is fetched from the chain in the
 * browser, so a stalled or wrong number is visible to anyone — a site that
 * claims to read a chain should prove it is still reading it.
 */

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const RPC = "https://rpc.mainnet.chain.robinhood.com";

const LINKS = [
  { href: "/launches", label: "Launches" },
  { href: "/method", label: "Method" },
];

function BlockChip() {
  const [block, setBlock] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    const read = async () => {
      try {
        const res = await fetch(RPC, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            jsonrpc: "2.0",
            id: 1,
            method: "eth_blockNumber",
            params: [],
          }),
        });
        const body = await res.json();
        if (!alive) return;
        if (body?.result) {
          setBlock(parseInt(body.result, 16));
          setFailed(false);
        } else {
          setFailed(true);
        }
      } catch {
        // Unreachable is not absent: say so rather than showing a stale
        // number as if it were current.
        if (alive) setFailed(true);
      }
    };
    read();
    const t = setInterval(read, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const label = failed
    ? "CHAIN UNREACHABLE"
    : block === null
      ? "READING CHAIN…"
      : `BLOCK ${block.toLocaleString("en-US")}`;

  return (
    <span
      className="data hidden items-center gap-2 text-[11px] tracking-[0.14em] sm:inline-flex"
      style={{ color: failed ? "var(--fail)" : "var(--ink-soft)" }}
      title={failed ? "Could not reach a Robinhood Chain RPC" : undefined}
    >
      <span
        aria-hidden
        className="block h-[6px] w-[6px] rounded-full"
        style={{
          background: failed ? "var(--fail)" : "var(--pass)",
          opacity: block === null && !failed ? 0.4 : 1,
        }}
      />
      {label}
    </span>
  );
}

export default function Nav() {
  const pathname = usePathname();
  // 0 = fully over the dark hero, 1 = fully over paper. Continuous, so the
  // bar changes with the section behind it instead of snapping at an
  // arbitrary scroll offset — the hero is 230vh tall, and a white bar
  // appearing over it forty pixels in was the jolt.
  const [t, setT] = useState(pathname === "/" ? 0 : 1);

  useEffect(() => {
    if (pathname !== "/") {
      setT(1);
      return;
    }
    const measure = () => {
      const hero = document.querySelector("[data-hero]") as HTMLElement | null;
      if (!hero) {
        setT(1);
        return;
      }
      const end = hero.offsetTop + hero.offsetHeight;
      const FADE = 220; // px of crossfade as the hero's last screen leaves
      const d = end - window.scrollY - 64; // 64 = bar height
      setT(Math.min(1, Math.max(0, 1 - d / FADE)));
    };
    measure();
    window.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
    };
  }, [pathname]);

  // Text must not spend the whole fade at half contrast: it flips over a
  // narrow window around the point where the paper sheet actually covers
  // the scrim, so labels stay readable on both sides of the transition.
  const step = (x: number) => {
    const u = Math.min(1, Math.max(0, (x - 0.42) / 0.22));
    return u * u * (3 - 2 * u);
  };
  const tText = step(t);
  const mix = (over: string, paper: string) =>
    `color-mix(in oklab, ${over} ${(1 - tText) * 100}%, ${paper})`;

  return (
    <header className="fixed inset-x-0 top-0 z-50">
      {/* Two stacked washes crossfade with the section behind the bar: a
          soft dark scrim over the hero, paper everywhere else. */}
      {/* The dark scrim stays put and the paper sheet fades in on top of
          it. Crossfading both at once left a half-transparent hole in the
          middle of the transition where the bar turned muddy. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, rgba(14,17,19,.92) 0%, rgba(14,17,19,.6) 62%, rgba(14,17,19,0) 100%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          opacity: t,
          background: "var(--paper)",
          borderBottom: "1px solid var(--hairline)",
        }}
      />
      <div className="relative mx-auto flex h-16 max-w-6xl items-center justify-between px-6 sm:px-10">
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/brand/gavel-mark-tight.png"
            alt="GAVEL"
            width={26}
            height={26}
            priority
          />
          <span
            className="data text-[11px] tracking-[0.22em]"
            style={{ color: mix("#d8c9a0", "var(--ink)") }}
          >
            GAVELSCAN
          </span>
        </Link>

        <nav className="flex items-center gap-7">
          {LINKS.map((l) => {
            const active = pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className="data text-[12px] tracking-[0.1em] transition-opacity hover:opacity-100"
                style={{
                  color: mix("#c9ccd1", active ? "var(--brass)" : "var(--ink-soft)"),
                  opacity: active ? 1 : 0.85,
                }}
              >
                {l.label}
              </Link>
            );
          })}
          <span
            aria-hidden
            className="hidden h-4 w-px sm:block"
            style={{ background: mix("#2a2e33", "var(--hairline)") }}
          />
          <span style={{ opacity: t }}>
            <BlockChip />
          </span>
        </nav>
      </div>
    </header>
  );
}
