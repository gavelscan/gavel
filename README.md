# GAVEL

**The verdict layer for onchain launch auctions.**
Read the gavel before you bid.

GAVEL watches every launch going through [Uniswap Liquidity
Launcher](https://github.com/Uniswap/liquidity-launcher) on Robinhood
Chain (4663), decodes the auction parameters most bidders never read, and
publishes a verdict — **PASS / FLAG / FAIL** — before the money moves.

Uniswap's own documentation warns that it is *"trivially easy to create a
LBPStrategy and corresponding Auction with malicious parameters"* and
tells users to *"validate all parameters"* themselves. GAVEL is that
validation, done properly, for every launch, in public.

**Live at [gavelscan.xyz](https://gavelscan.xyz)** — the record, one page
per launch, and a free JSON API. No token. No wallet-connect. GAVEL never
touches funds.

## How a verdict is made

1. **Facts** — deterministic checks decode `MigratorParameters` and read
   live chain state: where the money goes on every path, LP allocation
   schedule, pool commitment, recipient provenance, currency identity.
2. **Ceiling** — the facts set a verdict ceiling. Hard failures cap the
   verdict at FAIL, warnings at FLAG.
3. **Judgment** — the judge (an agent) reasons about what scripts cannot:
   hook economics, currency authenticity, deployer provenance. It may
   lower the verdict below the ceiling. **It can never raise it.**

A launch that fails a hard deterministic check can never be talked up to
PASS by a language model having a good day. That clamp is Invariant I3,
and the rest of the invariants live in [SPEC.md](./SPEC.md).

## What the record has already found

Every number below is recomputable from public chain state — that is the
point of the product, and the standard this repo holds itself to.

- **The chain emits no event when nobody bids.** An auction that draws no
  bids just sits past its migration block in silence, indistinguishable
  in the logs from one that cleared and was never migrated. The
  initializer's `lbpInitializationParams()` reverts until a clearing
  price exists — that revert is the missing event, and GAVEL calls it on
  every launch to tell the two apart.
- **The launcher is not being neglected; most launches draw no bids.**
  Roughly three in four auctions never reach a clearing price. Every
  auction that did clear was migrated — the count of cleared-but-
  abandoned launches is zero.
- **Most "contract" recipients are wallets.** 39 of the 40 code-bearing
  recipient addresses in the record are EIP-7702 delegated EOAs, not
  contracts. GAVEL labels them as what they are: wallets running
  delegated code.

## The API

### Free: the record as static JSON

Same data the site renders. No key, no rate limit, rebuilt from chain
state every few minutes.

```bash
curl https://gavelscan.xyz/v1/live.json        # auctions still open
curl https://gavelscan.xyz/v1/launches.json    # every recorded auction
curl https://gavelscan.xyz/v1/summary.json     # counts at the current head
```

Full endpoint list and field reference:
[gavelscan.xyz/api-docs](https://gavelscan.xyz/api-docs).

### Paid: x402, settled on the chain being watched

The free files are a snapshot. The paid lane reads the chain **at the
block your request lands on** — built for agents deciding during a live
auction, priced for machines:

```bash
curl https://gavelscan.xyz/api/x402/watch/<auction>
```

Called bare, it answers `HTTP 402` with a machine-readable price sheet
(`x402Version: 1`): 0.5 USDG on Robinhood Chain buys a 7-day pass. Paying
is four steps and none of them involve us:

1. Read the 402 challenge — it names the asset, amount and receiving
   address. The challenge, not this README, is the source of truth.
2. Send the USDG yourself, from any wallet whose key you hold. There is
   no contract of ours to call and nothing to approve.
3. Sign `gavel-pass:<your tx hash>` with the wallet that paid
   (`cast wallet sign` or any `personal_sign`).
4. Retry with `X-PAYMENT: <tx hash>.<signature>`.

Design properties, deliberate and load-bearing:

- **Stateless.** No account, no API key, no database. The transaction is
  the receipt; the signature proves the receipt is yours. Every transfer
  to the receiving address is public, so a bare hash would be a ticket
  anyone could photocopy off the explorer — the signature is what makes
  it a pass.
- **No custody, even of our own till.** The server holds no key. It can
  verify payments; it cannot spend them. Invariant I7 — GAVEL never
  touches funds — applied to the cash register.
- **No facilitator.** Payment settles as a plain USDG transfer on chain
  4663 and is verified by reading the receipt back off the chain. There
  is no third-party payment service that can quietly die under the
  endpoint.
- **An unreachable chain is a 503, never a rejection.** A payment the
  server cannot check is not a payment it can reject. Telling a paying
  caller their real transaction "was not found" because a node dropped a
  request is the one failure a stateless gate cannot walk back.

Known limit: signature recovery assumes an EOA payer (EIP-7702 delegated
wallets included). A smart-contract wallet (ERC-1271) cannot buy a pass
yet.

There is a live request panel at
[gavelscan.xyz/api-docs](https://gavelscan.xyz/api-docs) that fires real
requests at this endpoint from the page, including the bare 402.

## What runs where

| Piece | Where it lives |
|---|---|
| `gavel/` | Watcher, decoder, deterministic checks, verdict ceiling — Python, no web3 dependency |
| `agent/` | The judge: provider-agnostic model runtime behind policy gates that clamp its output to the ceiling |
| `card/` | Verdict and statement card renderers (PIL) — every published image is generated, never hand-edited |
| `site/` | Static Next.js export: the record, one page per launch, the free `/v1` JSON |
| `site/api/` | The only server code in the product: the x402 gate, as plain `.mjs` Vercel functions |
| `scripts/` | Feed/API/deployer builders and the refresh pipeline (launchd + GitHub Actions, reconciling writers) |

The record itself is generated: `site/src/app/*.json` and `site/public/v1/`
are build artifacts committed by the refresh pipeline, one commit per
block-stamped refresh.

## Run it yourself

```bash
python3 -m unittest discover -s tests        # test suite
python3 scripts/dry_run.py                   # factsheet for the fixture launch
python3 scripts/dry_run.py <launch_tx_hash>  # factsheet for any launch
```

Requires Python 3.9+, `eth-abi`, `requests`. Chain access via any
Robinhood Chain RPC (default: the public endpoint). Every verdict page on
the site lists the exact transaction, auction contract, token and
recipient it was derived from — not so the page looks thorough, but so
you can run the same calls and get the same answer without us.

## Docs

- [SPEC.md](./SPEC.md) — components, invariants, agent policy gates
- [THREAT_MODEL.md](./THREAT_MODEL.md) — our failure modes, written first
- [DEPLOY.md](./DEPLOY.md) — how the site, data pipeline and functions ship

## License

MIT
