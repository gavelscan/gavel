# GAVEL v0 "First Gavel" — Spec

The verdict layer for onchain launch auctions. GAVEL watches every launch
going through Uniswap's Liquidity Launcher on Robinhood Chain, gathers the
facts a bidder cannot be expected to decode by hand, and publishes a
verdict — PASS / FLAG / FAIL — before the money moves.

Uniswap's own docs say: *"You must validate all parameters set on each
contract in the system before interacting with them."* GAVEL is that
sentence, implemented.

## Components (build order)

| # | Component | Dir | Status |
|---|---|---|---|
| 1 | Decoder — events + `MigratorParameters` structs | `gavel/decode.py` | ✅ done, verified vs live tx |
| 2 | Chain client — raw JSON-RPC, no indexer trust | `gavel/chain.py` | ✅ done |
| 3 | Deterministic checks + verdict ceiling | `gavel/checks.py` | ✅ done |
| 4 | Watcher — poll loop over new launches | `gavel/watch.py` | ✅ done, full history archived |
| 5 | Judge — agent layer (see Agent spec) | `agent/` | ⬜ |
| 6 | Verdict card renderer + X posting | `card/` | ⬜ |
| 7 | Static feed site (gavelscan.xyz) | `site/` | ⬜ last |

No smart contracts in v0. No token. No wallet-connect. On-chain
attestations / x402 metering are explicitly out of scope until the demand
gate passes.

## Invariants

- **I1 — Chain is the only source of truth.** Every published claim
  anchors to data fetched from a direct RPC (`eth_getLogs`, `eth_call`,
  `eth_getCode`). No third-party indexer or price API as evidence.
- **I2 — Verdict domain is closed.** A verdict is exactly one of
  PASS / FLAG / FAIL. No scores, no percentages, no vibes.
- **I3 — The ceiling rule.** Deterministic checks produce a verdict
  *ceiling*. The judge may lower a verdict below the ceiling, never raise
  it. Enforced in code (`clamp_verdict`), tested exhaustively.
- **I4 — No partial verdicts.** If any fact in the factsheet cannot be
  resolved (RPC failure, undecodable log), no verdict is published for
  that launch. Unknown ≠ safe, and unknown ≠ dangerous.
- **I5 — Unreachable is not absent.** RPC/node failure surfaces as an
  error state, never as "no findings". (Lesson carried from HATCH: a dead
  RPC returns 503, not "not found".)
- **I6 — Untrusted strings stay data.** Token names, symbols, and any
  deployer-supplied metadata are attacker-controlled input. They are never
  interpolated into judge instructions as instructions.
- **I7 — GAVEL never touches funds.** No user keys, no custody, no
  wallet-connect. The only credential in the system is the X posting
  session. If every GAVEL process dies, nobody's money is affected —
  trivially provable because there is no path to money.

## Agent spec (the judge)

**Autonomous decisions the judge makes:**
1. Whether a nonzero hook's *economic* behavior is hostile (reads source
   or bytecode; ERC165 compliance is already checked deterministically —
   Uniswap's docs state that check "does not prove the hook's economic
   behavior is safe").
2. Whether the auction currency is what its name claims (real RHJ stock
   token vs impostor), using deployment provenance, not name matching.
3. Whether recipient/deployer wallet history changes the risk picture
   (provenance clustering, serial-deployer patterns).
4. The verdict prose: what a bidder should understand, in two sentences,
   with every number traceable to the factsheet.
5. Re-judging: verdicts update when on-chain state changes
   (`Migrated` / `MigrationFailed` / auction progress) — an updated
   verdict card links its predecessor. Never silent edits.

**Triggers:** on-chain events only (`InitializerCreated`,
`Migrated`, `MigrationFailed`). No user-initiated judging in v0.

**Hard boundaries (policy gates, enforced outside the model):**
- Output must validate against the verdict JSON schema; invalid → retry,
  then drop. The model cannot free-text its way onto the feed.
- `clamp_verdict` applied after the model answers (I3).
- Vocabulary deny-list on published text: no "buy", "sell", "gem",
  "moon", "guaranteed", price predictions, or any imperative directed at
  the reader's money. GAVEL describes launches; it never advises trades.
- Posting rate-limited; global kill switch via env flag; dry-run mode is
  the default until explicitly armed.
- Every number in the card must exist in the factsheet. The model cites;
  it does not compute.

**If the agent dies:** the feed stops updating. No funds at risk (I7).
Deterministic factsheets can still be generated headless.

## Test plan

Target bar: 107+ tests before the feed goes public. Current: 76.

- Unit: decoder edge cases, schedule/position/pool/recipient checks — ✅ started
- Fixture: real HOTDOG/COST launch receipt (block 23898781) — ✅
- Fork: factsheet build against live RHC mainnet state — ✅ (`scripts/dry_run.py`)
- Adversarial (before judge goes live): prompt injection via token
  name/symbol/description; schema-escape attempts; verdict-raise attempts
  (must be clamped); deny-list bypass attempts.
- Watcher: reorg lag, coverage-gap refusal, duplicate suppression (incl. intra-batch), torn-archive recovery, faithful getLogs fake — ✅
- CI on every push once the repo is public.

## Demand gate (before ANY monetization / token / contracts)

30 days of live feed. Evaluate: card engagement, inbound integrator
interest, verdict track record vs migration outcomes. Kill criteria are
written in the concept doc and are binding.

## Milestones

- [x] Spec + invariants written
- [x] Decoder + chain client + checks, tested (42 tests, fixture + live)
- [x] Watcher loop + launch archive (JSONL) — 2,214 events, full LL history on RHC
- [ ] Judge runtime + policy gates + adversarial tests (target: 107+ total)
- [ ] Verdict card renderer (brand: slate/brass, PASS/FLAG/FAIL stamp)
- [ ] X posting via @gavelscan (dry-run first, then armed)
- [ ] Static feed on gavelscan.xyz
- [ ] Public repo under github.com/gavelscan (English-only), CI green
- [ ] 30-day demand gate → decide: x402 API / attestations / token / K3 executor
