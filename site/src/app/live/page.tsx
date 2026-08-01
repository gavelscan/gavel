import type { Metadata } from "next";
import LiveBoard from "@/components/LiveBoard";
import { FEED, ROWS } from "@/lib/feed";

export const metadata: Metadata = {
  title: "Live auctions — GAVEL",
  description:
    "Launch auctions on Robinhood Chain that have not yet reached their migration block, corrected against the chain as you read.",
};

export default function Live() {
  // Everything past its migration block at build time is history; the
  // board re-reads the rest against the live head in the browser.
  const candidates = ROWS.filter((r) => r.state === "live");
  return <LiveBoard rows={candidates} builtAt={FEED.head} />;
}
