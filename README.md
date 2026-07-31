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

## How a verdict is made

1. **Facts** — deterministic checks decode `MigratorParameters` and read
   live chain state: where the money goes on every path, LP allocation
   schedule, pool commitment, recipient provenance, currency identity.
2. **Ceiling** — the facts set a verdict ceiling. Hard failures cap the
   verdict at FAIL, warnings at FLAG.
3. **Judgment** — the judge (an agent) reasons about what scripts cannot:
   hook economics, currency authenticity, deployer provenance. It may
   lower the verdict below the ceiling. **It can never raise it.**

No token. No wallet-connect. GAVEL never touches funds.

## Run

```bash
python3 -m unittest discover -s tests        # test suite
python3 scripts/dry_run.py                   # factsheet for the fixture launch
python3 scripts/dry_run.py <launch_tx_hash>  # factsheet for any launch
```

Requires Python 3.9+, `eth-abi`, `requests`. Chain access via any
Robinhood Chain RPC (default: public endpoint).

## Docs

- [SPEC.md](./SPEC.md) — components, invariants, agent policy gates
- [THREAT_MODEL.md](./THREAT_MODEL.md) — our failure modes, written first

## License

MIT
