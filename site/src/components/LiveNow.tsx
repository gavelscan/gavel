"use client";

/**
 * The one page that cannot afford a snapshot.
 *
 * Everything else on this site is history and can be a build old without
 * misleading anyone. An open auction cannot: a reader looking at it is
 * deciding whether to put money in, and a card saying "in auction" about
 * something that closed forty minutes ago is worse than no card. So this
 * component re-reads the chain in the browser and corrects the page.
 *
 * It does three things, in order of how much they matter:
 *   1. Drops auctions whose migration block has passed since the build.
 *   2. Recomputes how long each remaining one has.
 *   3. Reports launches created since the build that the snapshot cannot
 *      know about, without pretending to have judged them.
 *
 * It never invents a verdict. A launch discovered here is announced as
 * unread, because the deterministic checks run against a factsheet this
 * component does not build.
 */

import { useEffect, useState } from "react";
import { decodeAbiParameters, parseAbiParameters } from "viem";
import { FEED, LaunchRow } from "@/lib/feed";

const RPC = "https://rpc.mainnet.chain.robinhood.com";
const LBP_STRATEGY = "0x05d552391067389EE44fec3924157ed33F976000";
const TOPIC_INITIALIZER_CREATED =
  "0x6d759545eb439f07e70f45431d6339af7a4f1ffef06d43e8ddf47fdb0799708c";

/* Mirrors MigratorParameters in the audited source. Only the fields a
   reader needs before bidding are pulled out of it. */
const MIGRATOR_PARAMS = parseAbiParameters(
  "(address token, address currency, uint64 migrationBlock, uint128 reservedTokenAmountForLP, address recipient, address positionRecipient, (uint24 fee, int24 tickSpacing, address hook) pool, bytes positionDefinitions, bytes lpAllocationSchedule)",
);

export type LiveState = {
  head: number | null;
  /** Auctions from the build that are still open at the live head. */
  stillOpen: Set<string>;
  /** Auctions created since the build. Unjudged by construction. */
  fresh: { ini: string; token: string; migrationBlock: number; block: number }[];
  error: string | null;
};

async function rpc(method: string, params: unknown[]) {
  const res = await fetch(RPC, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  const body = await res.json();
  if (body?.error) throw new Error(body.error.message ?? "rpc error");
  if (body?.result === undefined) throw new Error("malformed rpc response");
  return body.result;
}

export function useLiveNow(rows: LaunchRow[]): LiveState {
  const [state, setState] = useState<LiveState>({
    head: null,
    stillOpen: new Set(rows.map((r) => r.ini.toLowerCase())),
    fresh: [],
    error: null,
  });

  useEffect(() => {
    let alive = true;

    const read = async () => {
      try {
        const head = Number(BigInt(await rpc("eth_blockNumber", [])));

        // 1 & 2: which of the built rows are still open right now.
        const stillOpen = new Set(
          rows
            .filter((r) => r.migration_block > head)
            .map((r) => r.ini.toLowerCase()),
        );

        // 3: anything created since the snapshot. One filtered log query.
        const logs: { topics: string[]; data: string; blockNumber: string }[] =
          await rpc("eth_getLogs", [
            {
              address: LBP_STRATEGY,
              topics: [TOPIC_INITIALIZER_CREATED],
              fromBlock: "0x" + (FEED.head + 1).toString(16),
              toBlock: "0x" + head.toString(16),
            },
          ]);

        const known = new Set(rows.map((r) => r.ini.toLowerCase()));
        const fresh: LiveState["fresh"] = [];
        for (const log of logs) {
          const ini = ("0x" + log.topics[1].slice(26)).toLowerCase();
          if (known.has(ini)) continue;
          try {
            const [p] = decodeAbiParameters(
              MIGRATOR_PARAMS,
              log.data as `0x${string}`,
            );
            const migrationBlock = Number(p.migrationBlock);
            if (migrationBlock <= head) continue; // already closed
            fresh.push({
              ini,
              token: p.token,
              migrationBlock,
              block: Number(BigInt(log.blockNumber)),
            });
          } catch {
            // An event we cannot decode is a protocol change, not a launch
            // to guess at. Skip it here; the watcher records it as unknown.
          }
        }

        if (alive) setState({ head, stillOpen, fresh, error: null });
      } catch (e) {
        // Unreachable is not absent (I5): say the read failed rather than
        // letting the stale page pass for a current one.
        if (alive)
          setState((s) => ({
            ...s,
            error: e instanceof Error ? e.message : "chain read failed",
          }));
      }
    };

    read();
    const t = setInterval(read, 12000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [rows]);

  return state;
}
