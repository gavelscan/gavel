/**
 * GET /api/x402/watch/<auction> — live auction state, read at request time.
 *
 * The whole reason this costs money: the free record is a snapshot that
 * refreshes every ~15 minutes, and a bidder deciding RIGHT NOW sits inside
 * that window. This endpoint asks the chain at the current block — has the
 * auction cleared, how much sold, how much raised, how many blocks remain —
 * and never serves a cached answer.
 *
 * Payment is the HATCH-proven x402 shape (see _lib/payment.ts): USDG on
 * Robinhood Chain, stateless pass, no facilitator. While no receiving
 * address is configured the endpoint runs in preview mode: free, and the
 * response says so.
 *
 * Plain .mjs with the classic (req, res) signature, on purpose: both the
 * Web-API export and compiled TypeScript died at module load in this
 * runtime (FUNCTION_INVOCATION_FAILED before any of our code ran). A
 * .mjs file has exactly one possible module format.
 */

import {
  ChainUnreachable,
  NodeError,
  PASS_DAYS,
  PREVIEW,
  challenge,
  rpc,
  verifyPayment,
} from "../_lib/payment.mjs";

const RESOURCE = "/api/x402/watch/{auction}";
const SEL_LBP_PARAMS = "0xe1d97d1f"; // lbpInitializationParams()

// The static record this deployment also serves. Fetched over HTTP because
// a Vercel function has no filesystem view of the static assets.
const RECORD_BASE = process.env.GAVEL_RECORD_BASE || "https://www.gavelscan.xyz";

function send(res, status, body) {
  res.setHeader("access-control-allow-origin", "*");
  res.setHeader("access-control-allow-headers", "x-payment");
  res.setHeader("access-control-allow-methods", "GET, OPTIONS");
  res.setHeader("cache-control", "no-store");
  res.status(status).json(body);
}

export default async function handler(req, res) {
  if (req.method === "OPTIONS") {
    res.setHeader("access-control-allow-origin", "*");
    res.setHeader("access-control-allow-headers", "x-payment");
    res.setHeader("access-control-allow-methods", "GET, OPTIONS");
    res.status(204).end();
    return;
  }

  const raw = req.query.auction;
  const auction = (Array.isArray(raw) ? raw[0] : raw ?? "").toLowerCase();
  if (!/^0x[0-9a-f]{40}$/.test(auction)) {
    send(res, 400, {
      error: "path must end in an auction (initializer) address",
      example: "/api/x402/watch/0xb4c0d8f1cc612487ac36cb07964683a882a43f02",
    });
    return;
  }

  // -- the toll booth ---------------------------------------------------
  let pass = null;
  if (!PREVIEW) {
    const h = req.headers["x-payment"];
    const header = Array.isArray(h) ? h[0] : h;
    if (!header) {
      send(res, 402, challenge(RESOURCE));
      return;
    }
    let payment;
    try {
      payment = await verifyPayment(header.trim());
    } catch (error) {
      if (!(error instanceof ChainUnreachable)) throw error;
      // A payment we cannot check is not a payment we can reject. When
      // the chain says nothing, say 503 and leave the caller's pass alone.
      send(res, 503, {
        error: "could not reach the chain to verify the payment",
        hint: "your transaction is fine; retry with the same X-PAYMENT header",
      });
      return;
    }
    if (!payment.ok) {
      send(res, 402, { ...challenge(RESOURCE), rejected: payment.reason });
      return;
    }
    pass = { payer: payment.payer, paidUsdg: payment.paidUsdg, expiresAt: payment.expiresAt };
  }

  // -- what our own record knows (context, not the product) --------------
  let record = null;
  try {
    const r = await fetch(`${RECORD_BASE}/v1/launch/${auction}.json`, { cache: "no-store" });
    if (r.ok) record = await r.json();
  } catch {
    record = null; // the record is garnish here; the chain is the answer
  }

  // -- the chain, right now ----------------------------------------------
  let head;
  let code;
  try {
    head = parseInt((await rpc("eth_blockNumber", [])) ?? "0x0", 16);
    code = await rpc("eth_getCode", [auction, "latest"]);
  } catch (error) {
    if (error instanceof ChainUnreachable || error instanceof NodeError) {
      send(res, 503, {
        error: "could not reach the chain",
        hint: "no answer is better than a stale one presented as live",
      });
      return;
    }
    throw error;
  }

  if (!code || code === "0x") {
    send(res, 404, {
      error: `no contract at ${auction} on chain 4663`,
      hint: record
        ? "our record knows this launch but the chain shows no code — check the address"
        : "not in our record either; is this an initializer address?",
    });
    return;
  }

  // The initializer reverts until a clearing price exists — the only way
  // to tell "nobody bid" from "nobody pressed the button". A revert is a
  // fact; only an unreachable node is an unknown.
  let cleared = false;
  let sold = null;
  let raised = null;
  try {
    const out = await rpc("eth_call", [
      { to: auction, data: SEL_LBP_PARAMS },
      "latest",
    ]);
    if (out && out.length >= 2 + 192) {
      const word = (i) => BigInt("0x" + out.slice(2 + 64 * i, 2 + 64 * (i + 1)));
      cleared = true;
      sold = word(1).toString();
      raised = word(2).toString();
    }
  } catch (error) {
    if (error instanceof ChainUnreachable) {
      send(res, 503, { error: "could not reach the chain" });
      return;
    }
    if (!(error instanceof NodeError)) throw error;
    cleared = false; // the node answered: reverted, so no clearing price yet
  }

  const migrationBlock = record?.migration_block ?? null;
  const blocksRemaining =
    migrationBlock !== null ? Math.max(0, migrationBlock - head) : null;

  send(res, 200, {
    auction,
    read_at_block: head,
    cleared,
    sold,
    raised,
    migration_block: migrationBlock,
    blocks_until_migration: blocksRemaining,
    record_state: record?.outcome ?? null,
    token: record?.token ?? null,
    verdict_page: record ? `${RECORD_BASE}/launch/${auction}` : null,
    note: cleared
      ? "a clearing price exists; sold and raised are read from the auction contract at this block"
      : "no clearing price at this block — lbpInitializationParams() still reverts",
    ...(PREVIEW
      ? {
          preview:
            "payment is not enabled yet; this response is free and will require " +
            `an x402 pass (USDG on chain 4663, ${PASS_DAYS}-day pass) once the ` +
            "receiving address is configured",
        }
      : { pass }),
  });
}
