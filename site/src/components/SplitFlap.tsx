"use client";

/**
 * A split-flap counter.
 *
 * The figures on this page describe a record that moves, and a number that
 * changes without saying so is easy to miss. Flipping the digits the way a
 * departures board does makes the change visible and says something true
 * about the thing: it is a board of arrivals, mechanically updated, not a
 * figure somebody typed.
 *
 * Only the digits that actually changed flip. Nothing flips on first paint,
 * because a page that opens mid-somersault is a novelty, not information.
 * Under reduced motion the number simply changes.
 */

import { useEffect, useRef, useState } from "react";

function Digit({ char, animate }: { char: string; animate: boolean }) {
  const [prev, setPrev] = useState(char);
  const [flipping, setFlipping] = useState(false);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      setPrev(char);
      return;
    }
    if (char === prev) return;
    if (!animate) {
      setPrev(char);
      return;
    }
    setFlipping(true);
    const t = setTimeout(() => {
      setPrev(char);
      setFlipping(false);
    }, 420);
    return () => clearTimeout(t);
  }, [char, prev, animate]);

  // Separators do not flip; they are punctuation, not values. They keep the
  // same box as a digit all the same — an inline-block that clips its
  // overflow takes its baseline from its bottom edge, so a bare comma
  // beside clipped digits sits several pixels low.
  if (!/\d/.test(char)) {
    return (
      <span className="relative inline-block overflow-hidden tabular-nums">
        {char}
      </span>
    );
  }

  return (
    <span className="relative inline-block overflow-hidden tabular-nums">
      {/* The outgoing digit falls away; the incoming one drops in behind it. */}
      <span
        className="block"
        style={{
          transition: flipping ? "transform .42s cubic-bezier(.2,.7,.3,1), opacity .42s" : undefined,
          transform: flipping ? "translateY(-100%) rotateX(-70deg)" : "none",
          opacity: flipping ? 0 : 1,
          transformOrigin: "bottom center",
        }}
      >
        {prev}
      </span>
      {flipping && (
        <span
          aria-hidden
          className="absolute inset-0 block"
          style={{
            animation: "gavel-flap .42s cubic-bezier(.2,.7,.3,1) forwards",
            transformOrigin: "top center",
          }}
        >
          {char}
        </span>
      )}
    </span>
  );
}

export default function SplitFlap({
  value,
  className = "",
}: {
  value: number | string;
  className?: string;
}) {
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    setAnimate(!window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  const text =
    typeof value === "number" ? value.toLocaleString("en-US") : String(value);

  return (
    <span className={className} aria-label={text}>
      {text.split("").map((c, i) => (
        <Digit key={`${i}-${text.length}`} char={c} animate={animate} />
      ))}
    </span>
  );
}
