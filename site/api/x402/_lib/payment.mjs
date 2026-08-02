/* Plain ESM (.mjs) on purpose: the TypeScript versions of these functions
 * died at module load with FUNCTION_INVOCATION_FAILED — the compiled ESM
 * was being executed as CommonJS. A .mjs file has exactly one possible
 * module format, so this entire failure class is gone.
 *
 * Payment verification for GAVEL's x402 endpoints.
 *
 * Ported from HATCH (lastout-x402/web/lib/payment.ts), where this shape ran
 * first: no database, no hot wallet, no facilitator. A caller pays USDG to
 * the receiving address themselves and presents the transaction hash; the
 * server reads that transaction back off the chain and decides. The chain is
 * the ledger — anyone can audit who paid and when without asking us, and
 * there is no key here for anyone to steal. That is the same property the
 * rest of GAVEL sells (Invariant I7: we never touch funds), applied to our
 * own till: the server can VERIFY payments but cannot spend them.
 *
 * PREVIEW MODE exists for a window like the one before this address
 * landed: with no address configured the endpoint serves answers free,
 * loudly marked. Setting GAVEL_PAY_TO="" would re-enter it deliberately;
 * a deploy can no longer enter it by accident.
 */

const RPC = process.env.RHC_RPC || "https://rpc.mainnet.chain.robinhood.com";
const USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168";
const TRANSFER_TOPIC =
  "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef";

/** Where callers pay.
 *
 *  In the source rather than in an environment variable, deliberately
 *  (HATCH's lesson): every 402 response publishes this address anyway, so
 *  hiding it buys nothing — and a variable missing from a deploy would
 *  leave the endpoint quietly refusing real payments with no way for
 *  anyone outside to tell why. Here it is versioned and diffable.
 *  Checksum verified and confirmed a fresh EOA before it landed. Not the
 *  HATCH address — one till per product. */
const DEFAULT_PAY_TO = "0x60630a291130621E3af22F6c1E2FA4D5F5429667";

export const PAY_TO = (process.env.GAVEL_PAY_TO || DEFAULT_PAY_TO).toLowerCase();
export const PREVIEW = PAY_TO === "";

export const PRICE_USDG = Number(process.env.GAVEL_PRICE_USDG ?? "0.5");
export const PASS_DAYS = Number(process.env.GAVEL_PASS_DAYS ?? "7");

/** The node did not answer. Not the same as the thing not existing — a
 *  payment gate that conflates the two tells a paying caller their real
 *  transaction "was not found" and burns their pass (Invariant I5, at the
 *  cash register). */
export class ChainUnreachable extends Error {}

export async function rpc(method, params) {
  let response;
  try {
    response = await fetch(RPC, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
      cache: "no-store",
    });
  } catch {
    throw new ChainUnreachable(method);
  }
  const payload = await response.json().catch(() => null);
  if (!payload) throw new ChainUnreachable(method);
  if (payload.error) {
    // The node answered with an error. For eth_call that is usually a
    // revert, which is a fact about the contract, not an outage — the
    // caller decides what a node error means for its method.
    throw new NodeError(String(payload.error?.message ?? "node error"));
  }
  return payload.result ?? null;
}

/** The node answered, and the answer was an error. Distinct from
 *  ChainUnreachable so a revert is never treated as an outage. */
export class NodeError extends Error {}

/** The string a payer signs to claim their transaction as a pass. */
export function passMessage(txHash) {
  return `gavel-pass:${txHash.toLowerCase()}`;
}

/**
 * A pass is a USDG transfer to PAY_TO, at least PRICE_USDG, within the
 * window — PLUS a signature over passMessage(hash) from the wallet that
 * sent it. The signature is what stops freeloading: every transfer to
 * PAY_TO is public, so a bare hash is a ticket anyone can photocopy off
 * the explorer. The signature can only come from the key that paid, and
 * it never appears on chain.
 *
 * Known limit, carried over from HATCH: recovery assumes an EOA payer
 * (EIP-7702 delegated wallets included — the key still signs). A
 * smart-contract wallet (ERC-1271) cannot produce a recoverable
 * signature; support it when someone actually pays from one.
 */
export async function verifyPayment(header) {
  const [txHash, signature] = header.split(".");
  if (!/^0x[0-9a-fA-F]{64}$/.test(txHash ?? "")) {
    return { ok: false, reason: "X-PAYMENT must be <transaction hash>.<signature>" };
  }
  if (!/^0x[0-9a-fA-F]{130}$/.test(signature ?? "")) {
    return {
      ok: false,
      reason:
        `signature missing or malformed. sign the exact string "${passMessage(txHash)}" ` +
        "with the wallet that paid, then send X-PAYMENT: <hash>.<signature>",
    };
  }

  let receipt;
  try {
    receipt = await rpc("eth_getTransactionReceipt", [txHash]);
  } catch (e) {
    if (e instanceof NodeError) throw new ChainUnreachable("eth_getTransactionReceipt");
    throw e;
  }

  if (!receipt) return { ok: false, reason: "transaction not found on chain 4663" };
  if (receipt.status !== "0x1") return { ok: false, reason: "transaction reverted" };

  const paid = receipt.logs.find(
    (log) =>
      log.address.toLowerCase() === USDG &&
      log.topics[0] === TRANSFER_TOPIC &&
      log.topics.length >= 3 &&
      "0x" + log.topics[2].slice(-40).toLowerCase() === PAY_TO,
  );
  if (!paid) return { ok: false, reason: `no USDG transfer to ${PAY_TO} in this transaction` };

  const amount = Number(BigInt(paid.data)) / 1e6;
  if (amount < PRICE_USDG) {
    return { ok: false, reason: `paid ${amount} USDG, price is ${PRICE_USDG}` };
  }

  // The payer is whoever the token contract says sent the USDG — not
  // tx.from, which could be a router. The signature must recover to
  // exactly that address, or this is someone waving a stranger's receipt.
  const payer = "0x" + paid.topics[1].slice(-40);
  let signer;
  try {
    // Lazy so the module loads even if the bundler mishandles viem's ESM
    // graph — preview mode and the challenge path never need it at all.
    const { recoverMessageAddress } = await import("viem");
    signer = await recoverMessageAddress({
      message: passMessage(txHash),
      signature,
    });
  } catch {
    return { ok: false, reason: "signature does not parse" };
  }
  if (signer.toLowerCase() !== payer.toLowerCase()) {
    return {
      ok: false,
      reason: `signature recovers to ${signer}, but the USDG came from ${payer}`,
    };
  }

  let block;
  try {
    block = await rpc("eth_getBlockByNumber", [receipt.blockNumber, false]);
  } catch (e) {
    if (e instanceof NodeError) throw new ChainUnreachable("eth_getBlockByNumber");
    throw e;
  }
  if (!block) return { ok: false, reason: "could not read the block" };

  const paidAt = Number(BigInt(block.timestamp)) * 1000;
  const expiresAt = paidAt + PASS_DAYS * 86_400_000;
  if (Date.now() > expiresAt) {
    return { ok: false, reason: `pass expired ${new Date(expiresAt).toISOString()}` };
  }

  return {
    ok: true,
    payer,
    paidUsdg: amount,
    expiresAt: new Date(expiresAt).toISOString(),
  };
}

export function challenge(resource) {
  return {
    x402Version: 1,
    error: "payment required",
    accepts: [
      {
        scheme: "exact",
        network: "eip155:4663",
        asset: USDG,
        assetSymbol: "USDG",
        maxAmountRequired: String(Math.round(PRICE_USDG * 1e6)),
        payTo: PAY_TO,
        resource,
        description: `${PASS_DAYS}-day pass to ${resource}`,
        mimeType: "application/json",
      },
    ],
    howToPay: [
      `Send ${PRICE_USDG} USDG to ${PAY_TO} on Robinhood Chain (4663).`,
      'Sign the string  gavel-pass:<your tx hash>  with the wallet that paid (personal_sign, or: cast wallet sign "gavel-pass:0x...").',
      "Retry this request with header  X-PAYMENT: <tx hash>.<signature>",
      `The pass lasts ${PASS_DAYS} days from the block your payment landed in.`,
      "No account, no API key. The transaction is the receipt; the signature proves the receipt is yours — every transfer to this address is public, so a bare hash would be a ticket anyone could photocopy.",
    ],
  };
}
