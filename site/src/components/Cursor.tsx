"use client";

/**
 * A reader marking a record.
 *
 * The pointer becomes a small brass dot that draws a short ink stroke as
 * it moves and dries out behind it — the same trailing-canvas technique used
 * for the streaks on HATCH, turned into annotation. Over anything
 * interactive the nib opens into a bracket, the mark an editor puts around
 * the thing they are pointing at.
 *
 * Rules it obeys, because a custom cursor is a liability if it does not:
 * only on devices with a fine pointer, never on touch; nothing drawn when
 * reduced motion is requested; the native cursor is restored over text
 * inputs so a reader can still see where they are typing.
 */

import { useEffect, useRef } from "react";

const BRASS = "185, 141, 43";
const TRAIL_FADE = 0.13; // higher dries the ink faster
const MAX_POINTS = 26;

export default function Cursor() {
  const nib = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const fine = window.matchMedia("(pointer: fine)").matches;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!fine || still) return;

    document.documentElement.classList.add("has-nib");

    const el = nib.current!;
    const cv = canvas.current!;
    const ctx = cv.getContext("2d")!;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      cv.width = window.innerWidth * dpr;
      cv.height = window.innerHeight * dpr;
      cv.style.width = window.innerWidth + "px";
      cv.style.height = window.innerHeight + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    let x = -100, y = -100, px = -100, py = -100;
    let over = false, down = false;
    const pts: { x: number; y: number; life: number }[] = [];

    const onMove = (e: PointerEvent) => {
      x = e.clientX;
      y = e.clientY;
      const t = e.target as HTMLElement | null;
      over = !!t?.closest("a, button, [role='button'], input, summary");
      // Typing needs the real caret; step aside entirely.
      const typing = !!t?.closest("input, textarea");
      document.documentElement.classList.toggle("nib-off", typing);
    };
    const onDown = () => (down = true);
    const onUp = () => (down = false);
    const onLeave = () => {
      x = -100;
      y = -100;
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerdown", onDown, { passive: true });
    window.addEventListener("pointerup", onUp, { passive: true });
    window.addEventListener("pointerleave", onLeave);
    window.addEventListener("resize", resize);

    let raf = 0;
    const frame = () => {
      // The nib itself lags very slightly, the way a hand does.
      px += (x - px) * 0.35;
      py += (y - py) * 0.35;
      const scale = down ? 0.75 : over ? 1.15 : 1;
      el.style.transform = `translate3d(${px - 9}px, ${py - 9}px, 0) scale(${scale})`;
      el.style.opacity = x < 0 ? "0" : "1";
      el.dataset.over = String(over);

      // Ink: a stroke that dries from the tail.
      const last = pts[pts.length - 1];
      const moved = !last || Math.hypot(px - last.x, py - last.y) > 1.4;
      if (moved && x > 0) pts.push({ x: px, y: py, life: 1 });
      while (pts.length > MAX_POINTS) pts.shift();

      ctx.clearRect(0, 0, cv.width, cv.height);
      for (let i = 1; i < pts.length; i++) {
        const a = pts[i - 1], b = pts[i];
        const t = i / pts.length;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = `rgba(${BRASS}, ${0.5 * t * b.life})`;
        ctx.lineWidth = 1.6 * t + 0.3;
        ctx.lineCap = "round";
        ctx.stroke();
      }
      for (const p of pts) p.life -= TRAIL_FADE * 0.35;
      while (pts.length && pts[0].life <= 0) pts.shift();

      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      document.documentElement.classList.remove("has-nib", "nib-off");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <>
      <canvas
        ref={canvas}
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[90] hidden [.has-nib_&]:block [.nib-off_&]:hidden"
      />
      <div
        ref={nib}
        aria-hidden
        className="nib pointer-events-none fixed left-0 top-0 z-[91] hidden h-[18px] w-[18px] [.has-nib_&]:block [.nib-off_&]:hidden"
      >
        {/* A dot, which cannot be misread as a character the way an
            angled stroke on a word can. It opens into a ring over
            anything interactive; the element itself does the announcing. */}
        <span className="nib-stroke" />
      </div>
    </>
  );
}
