"use client";

/**
 * The header reads as the top of a document, not a marketing bar: a
 * hairline rule, monospaced labels, and a live block height on the right.
 *
 * The block number is the point. It is fetched from the chain in the
 * browser, so a stalled or wrong number is visible to anyone — a site that
 * claims to read a chain should prove it is still reading it. On small
 * screens it moves into the menu sheet rather than disappearing, because
 * hiding the proof of life on the device most readers use would defeat it.
 */

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { FEED } from "@/lib/feed";

const RPC = "https://rpc.mainnet.chain.robinhood.com";

const LINKS = [
  { href: "/live", label: "Live" },
  { href: "/launches", label: "Record" },
  { href: "/deployers", label: "Deployers" },
  { href: "/method", label: "Method" },
];

/* Secondary destinations: real, but not what a reader arrives for. */
const SECONDARY = [
  { href: "/api-docs", label: "API" },
  { href: "/changelog", label: "Changelog" },
];

function useBlockHeight() {
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

  return { block, failed, pending: block === null && !failed };
}

/* Blocks are sub-second on this chain; this is only used to phrase a gap
   in human terms, and it is always shown next to the raw block numbers. */
const SECONDS_PER_BLOCK = 0.25;

function age(blocks: number) {
  const m = Math.round((blocks * SECONDS_PER_BLOCK) / 60);
  if (m < 1) return "current";
  if (m < 60) return `${m} min behind`;
  const h = Math.round(m / 60);
  return h < 48 ? `${h} h behind` : `${Math.round(h / 24)} d behind`;
}

/**
 * Freshness, not liveness.
 *
 * Showing the live chain head alone was quietly misleading: the pages are
 * built from a snapshot, so a reader saw a number ticking up and assumed
 * the record was keeping pace with it. The chip now reports the block the
 * DATA was read at and how far behind the chain that leaves it, and turns
 * amber once the gap is wide enough to matter.
 */
function BlockChip({ className = "" }: { className?: string }) {
  const { block, failed, pending } = useBlockHeight();
  const gap = block === null ? null : Math.max(0, block - FEED.head);
  const stale = gap !== null && gap > 7200; // ~30 minutes

  const label = failed
    ? "CHAIN UNREACHABLE"
    : pending
      ? `DATA AT ${FEED.head.toLocaleString("en-US")}`
      : `DATA AT ${FEED.head.toLocaleString("en-US")} · ${age(gap!)}`;

  const tone = failed
    ? "var(--fail)"
    : stale
      ? "var(--brass)"
      : "var(--ink-soft)";

  return (
    <span
      className={`data inline-flex items-center gap-2 text-[11px] tracking-[0.14em] ${className}`}
      style={{ color: tone }}
      title={
        failed
          ? "Could not reach a Robinhood Chain RPC"
          : block === null
            ? undefined
            : `Chain head ${block.toLocaleString("en-US")}; this build was read at ${FEED.head.toLocaleString("en-US")}`
      }
    >
      <span
        aria-hidden
        className="block h-[6px] w-[6px] rounded-full"
        style={{
          background: failed
            ? "var(--fail)"
            : stale
              ? "var(--brass)"
              : "var(--pass)",
          opacity: pending ? 0.4 : 1,
        }}
      />
      {label}
    </span>
  );
}

/** Three hairlines — the same rules used everywhere else on the page —
 *  folding into a cross. */
function MenuIcon({ open, tone }: { open: boolean; tone: string }) {
  const bar =
    "absolute left-0 block h-[1.5px] w-full transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]";
  return (
    <span aria-hidden className="relative block h-[14px] w-[22px]">
      <span
        className={bar}
        style={{
          background: tone,
          top: 0,
          transform: open ? "translateY(6px) rotate(45deg)" : "none",
        }}
      />
      <span
        className={bar}
        style={{ background: tone, top: 6, opacity: open ? 0 : 1 }}
      />
      <span
        className={bar}
        style={{
          background: tone,
          top: 12,
          transform: open ? "translateY(-6px) rotate(-45deg)" : "none",
        }}
      />
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
  const [open, setOpen] = useState(false);

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

  // Close on route change and on Escape; lock the page behind the sheet.
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Text must not spend the whole fade at half contrast: it flips over a
  // narrow window around the point where the paper sheet actually covers
  // the scrim, so labels stay readable on both sides of the transition.
  const step = (x: number) => {
    const u = Math.min(1, Math.max(0, (x - 0.42) / 0.22));
    return u * u * (3 - 2 * u);
  };
  // With the sheet open the bar is paper, whatever is behind it.
  const tText = open ? 1 : step(t);
  const tBg = open ? 1 : t;
  const mix = useCallback(
    (over: string, paper: string) =>
      `color-mix(in oklab, ${over} ${(1 - tText) * 100}%, ${paper})`,
    [tText],
  );

  return (
    <header className="fixed inset-x-0 top-0 z-50">
      {/* The dark scrim stays put and the paper sheet fades in on top of
          it. Crossfading both at once left a half-transparent hole in the
          middle of the transition where the bar turned muddy. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, rgba(23,19,14,.94) 0%, rgba(23,19,14,.62) 62%, rgba(23,19,14,0) 100%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 transition-opacity duration-300"
        style={{
          opacity: tBg,
          background: "var(--paper)",
          borderBottom: "1px solid var(--hairline)",
        }}
      />

      <div className="relative mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-10">
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

        {/* Desktop and tablet */}
        <nav className="hidden items-center gap-6 lg:flex">
          {LINKS.map((l) => {
            const active = pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className="navlink data text-[12px] tracking-[0.1em]"
                data-active={active}
                style={{
                  color: active
                    ? mix("#e0cf9a", "var(--brass)")
                    : mix("#cbbfa8", "var(--ink-soft)"),
                }}
              >
                {l.label}
              </Link>
            );
          })}
          <span
            aria-hidden
            className="h-4 w-px"
            style={{ background: mix("#33291d", "var(--hairline)") }}
          />
          {SECONDARY.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="navlink data text-[12px] tracking-[0.1em] opacity-75"
              style={{ color: mix("#cbbfa8", "var(--ink-soft)") }}
            >
              {l.label}
            </Link>
          ))}
          <span
            aria-hidden
            className="h-4 w-px"
            style={{ background: mix("#33291d", "var(--hairline)") }}
          />
          <span style={{ opacity: t }}>
            <BlockChip />
          </span>
        </nav>

        {/* Small screens */}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls="nav-sheet"
          aria-label={open ? "Close menu" : "Open menu"}
          className="-mr-2 grid h-11 w-11 place-items-center lg:hidden"
        >
          <MenuIcon open={open} tone={mix("#efe8da", "var(--ink)")} />
        </button>
      </div>

      {/* The sheet unfolds the header rather than dropping a modal on the
          page, so the bar and the menu stay one object. */}
      <div
        id="nav-sheet"
        className="relative overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] lg:hidden"
        style={{
          maxHeight: open ? 560 : 0,
          opacity: open ? 1 : 0,
          background: "var(--paper)",
          borderBottom: open ? "1px solid var(--hairline)" : "none",
        }}
      >
        <nav className="flex flex-col px-5 pb-6 pt-1">
          {LINKS.map((l) => {
            const active = pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="display border-b border-hairline py-3.5 text-[1.5rem]"
                style={{ color: active ? "var(--brass)" : "var(--ink)" }}
              >
                {l.label}
              </Link>
            );
          })}
          {SECONDARY.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="data border-b border-hairline py-3.5 text-[12px] tracking-[0.12em] text-ink-soft"
            >
              {l.label.toUpperCase()}
            </Link>
          ))}
          <a
            href="https://github.com/gavelscan/gavel"
            className="data border-b border-hairline py-3.5 text-[12px] tracking-[0.12em] text-ink-soft"
          >
            SOURCE ↗
          </a>
          <BlockChip className="pt-5" />
        </nav>
      </div>
    </header>
  );
}
