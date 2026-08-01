"""Deterministic fact gathering + the verdict ceiling.

The split that keeps GAVEL honest (and not another rule-engine-with-a-
mascot): this module produces FACTS and a CEILING. It never produces the
final verdict. The judge (agent) reasons on top and may only lower the
verdict below the ceiling — never raise it (Invariant I3). A launch that
fails a hard deterministic check can never be talked up to PASS by a
language model having a good day.

Verdict ordering: PASS > FLAG > FAIL.
"""

from typing import Optional

from . import registry
from .chain import Rpc
from .constants import (
    DYNAMIC_FEE_FLAG,
    MAX_BRACKET_RATE,
    MAX_BRACKETS,
    MAX_LP_FEE,
    MAX_TICK,
    MIN_TICK,
    ZERO_ADDRESS,
)

PASS, FLAG, FAIL = "PASS", "FLAG", "FAIL"

# INFO is recorded and displayed but does NOT move the ceiling. It exists
# because the first calibration flagged conditions that are simply the base
# rate — 85% of launches pay an ordinary EOA — and a signal that fires on
# five launches in six is not a signal, it is a broken smoke alarm. What
# earns a FLAG has to be unusual; what earns a FAIL has to be structural.
INFO = "INFO"
_ORDER = {PASS: 2, FLAG: 1, FAIL: 0}


def affects_ceiling(severity: str) -> bool:
    return severity in _ORDER

# Official RHJ stock-token registry (chain 4663). Membership makes
# "official stock token" a FACT rather than a name-pattern guess — an
# impostor can copy the name "Costco • Robinhood Token" but cannot land on
# the registered address. See gavel/registry.py for the three-state
# contract: an unusable cache yields UNKNOWN, never "not official".
RHJ_REGISTRY = registry.load()


def worse(a: str, b: str) -> str:
    return a if _ORDER[a] <= _ORDER[b] else b


def clamp_verdict(agent_verdict: str, ceiling: str) -> str:
    """Invariant I3: the agent may lower, never raise."""
    return worse(agent_verdict, ceiling)


# -- pure checks (no network) -------------------------------------------------

def check_schedule(brackets: list) -> list:
    """Mirror of MigratorParams._validateLpAllocationSchedule plus economics.

    On-chain validation already rejects malformed schedules, so a violation
    here on a real event means our decoder or their contract changed —
    both are FAIL-and-alert, not shrug.
    """
    findings = []
    n = len(brackets)
    if n == 0 or n > MAX_BRACKETS:
        return [("schedule_invalid_count", FAIL, "bracket count %d" % n)]
    prev = -1
    for i, b in enumerate(brackets):
        if b["rate"] == 0 or b["rate"] > MAX_BRACKET_RATE:
            findings.append(("schedule_invalid_rate", FAIL, "bracket %d rate %d" % (i, b["rate"])))
        if i == 0 and b["lowerThreshold"] != 0:
            findings.append(("schedule_first_threshold", FAIL, "first lowerThreshold != 0"))
        if i > 0 and b["lowerThreshold"] <= prev:
            findings.append(("schedule_not_ascending", FAIL, "bracket %d" % i))
        prev = b["lowerThreshold"]

    # Where the money goes. The top bracket's rate applies to the bulk of a
    # successful raise, so it is the closest thing to "how much of what you
    # bid becomes liquidity". Routing all of it is the norm (83% of the
    # record), which is why only the shortfalls are worth saying.
    terminal = brackets[-1]["rate"] / MAX_BRACKET_RATE
    pct = terminal * 100
    if terminal < 0.05:
        findings.append((
            "exit_drain", FAIL,
            "only %.1f%% of the raise is routed to liquidity; the rest exits to the recipient" % pct,
        ))
    elif terminal < 0.50:
        findings.append((
            "exit_heavy", FLAG,
            "%.0f%% of the raise is routed to liquidity; the remainder exits to the recipient" % pct,
        ))
    elif terminal < 0.95:
        findings.append((
            "exit_partial", INFO,
            "%.0f%% of the raise is routed to liquidity" % pct,
        ))
    return findings


def check_positions(defs: list) -> list:
    findings = []
    if not defs:
        # No explicit positions: everything rides the implicit full-range
        # fallback. Valid per contract; nothing to flag by itself.
        return findings
    total_weight = sum(d["weight"] for d in defs)
    if total_weight > MAX_BRACKET_RATE:
        findings.append(("positions_weight_overflow", FAIL, "weights sum %d > 1e7" % total_weight))
    for i, d in enumerate(defs):
        full_range = d["offsetLower"] == MIN_TICK and d["offsetUpper"] == MAX_TICK
        if not full_range and d["offsetLower"] >= d["offsetUpper"]:
            findings.append(("position_inverted_range", FAIL, "position %d lower >= upper" % i))
    return findings


def check_pool(pool: dict) -> list:
    findings = []
    fee = pool["fee"]
    if fee == DYNAMIC_FEE_FLAG:
        findings.append(("pool_dynamic_fee", FLAG, "dynamic fee — fee logic lives in the hook"))
    elif fee > MAX_LP_FEE:
        findings.append(("pool_invalid_fee", FAIL, "fee %d > max" % fee))
    elif fee > 100_000:  # >10% LP fee: legal, hostile
        findings.append(("pool_extreme_fee", FLAG,
                         "committed pool charges a %.1f%% LP fee" % (fee / 10_000)))
    elif fee > 20_000:  # 2-10%: high but used
        findings.append(("pool_high_fee", INFO,
                         "committed pool charges a %.1f%% LP fee" % (fee / 10_000)))
    if pool["hook"] != ZERO_ADDRESS:
        findings.append(("pool_nonzero_hook", FLAG,
                         "custom hook %s — economic behavior needs judgment" % pool["hook"]))
    return findings


# -- networked facts ----------------------------------------------------------

def gather_address_facts(rpc: Rpc, address: str) -> dict:
    code = rpc.call("eth_getCode", [address, "latest"])
    return {
        "address": address,
        "code_size": max(0, len(code) // 2 - 1),
        # EIP-7702: an account whose code is exactly the 23-byte indicator
        # 0xef0100 || <20-byte implementation> is not a contract. It is an
        # ordinary wallet that has delegated execution, and its owner still
        # holds the key. Treating it as a contract was reporting "raised
        # funds are routed to a contract" on 75 launches whose recipient is
        # a person's wallet — 39 of the 40 code-bearing recipients in the
        # record are these.
        "delegated": code[:8].lower() == "0xef0100" and len(code) == 48,
        "delegate": "0x" + code[8:48] if len(code) == 48 else None,
        "nonce": rpc.get_nonce(address),
        "balance_wei": rpc.get_balance(address),
    }


def check_recipient(facts: dict) -> list:
    """Paying an ordinary EOA is what 85% of launches do; saying so is
    context, not a warning. A recipient with almost no history is the
    unusual shape, and that is what gets flagged."""
    if facts["code_size"] > 0 and not facts.get("delegated"):
        return [("recipient_contract", INFO,
                 "raised funds are routed to a contract")]
    nonce = facts["nonce"]
    if facts.get("delegated"):
        # Still a wallet, so the history checks below would apply — but a
        # delegated account's nonce is spent by its delegate as well as by
        # its owner, so "no history" no longer means what it means for a
        # plain EOA. Report the fact and claim nothing about the history.
        return [("recipient_delegated_wallet", INFO,
                 "raised funds are routed to a wallet running delegated "
                 "code (EIP-7702)")]
    if nonce == 0:
        return [("recipient_fresh", FLAG,
                 "recipient wallet has never sent a transaction")]
    if nonce < 3:
        return [("recipient_new", FLAG,
                 "recipient wallet has almost no history (%d prior transactions)" % nonce)]
    return [("recipient_eoa", INFO,
             "recipient is a wallet with %d prior transactions" % nonce)]


def check_currency(rpc: Rpc, currency: str) -> dict:
    """Facts about the auction currency. Judgment about authenticity
    (real RHJ stock token vs impostor) belongs to the judge, not here."""
    if currency == ZERO_ADDRESS:
        return {"kind": "native_eth", "official": False,
                "registry_status": registry.UNKNOWN,
                "findings": [("currency_native", INFO,
                              "auction is priced in native ETH")]}
    reg_status = RHJ_REGISTRY.status(currency)
    official = RHJ_REGISTRY.get(currency)
    facts = {
        "kind": "erc20",
        "symbol": rpc.read_string(currency, Rpc.SEL_SYMBOL),
        "name": rpc.read_string(currency, Rpc.SEL_NAME),
        "code_size": rpc.get_code_size(currency),
        "official": reg_status == registry.MEMBER,
        "registry_status": reg_status,
        "official_symbol": official["symbol"] if official else None,
        "findings": [],
    }
    if facts["code_size"] == 0:
        facts["findings"].append(("currency_no_code", FAIL, "currency has no bytecode"))

    name = facts["name"] or ""
    if official:
        # Address is in the official registry: authenticity is a fact.
        facts["findings"].append((
            "currency_official_stock", PASS,
            "auction currency is an official Robinhood stock token (%s), verified by registered address"
            % official["symbol"],
        ))
    elif name.endswith("Robinhood Token"):
        if reg_status == registry.NON_MEMBER:
            # Claims the name but the address is NOT registered — the
            # impostor shape, and this is an accusation we can stand behind
            # only because the registry was actually readable.
            facts["findings"].append((
                "currency_impostor_claim", FAIL,
                "currency name claims an official Robinhood stock token, but its address is not in the registry",
            ))
        else:
            facts["findings"].append((
                "currency_registry_unavailable", FLAG,
                "currency claims an official Robinhood stock token, but the issuer registry could not be read to confirm it",
            ))
    else:
        facts["findings"].append((
            "currency_nonstandard", FLAG,
            "auction priced in arbitrary ERC20 %r — value of the raise depends on it" % (facts["symbol"],),
        ))
    return facts


# -- assembly -----------------------------------------------------------------

# check_overhang lived here and has been withdrawn. Keeping the reason,
# because the mistake is easy to make again:
#
# It computed how much of a token the deployer could sell into the pool as
#     unsold = totalSupply - reservedTokenAmountForLP - sold
#     depths = unsold / reservedTokenAmountForLP
# and every term in that is the wrong quantity.
#
#  - The numerator counts supply that was never in the auction. The LBP is
#    endowed with distribution.amount, an arbitrary figure chosen by the
#    caller; it has no relation to the ERC20's totalSupply. The leftover
#    the check wanted is initializer.totalSupply() - sold.
#  - The denominator is not the pool's token balance. Part of the reserve
#    is swept back out during migration, so the pool receives
#    reservedTokenAmountForLP - TokensSwept.amount.
#  - The holder is not "the deployer". Unsold auction tokens stay in the
#    initializer and are claimed by tokensRecipient(), a separate
#    parameter, and MigratorParameters.recipient differs from the launch
#    tx sender on 11 of 105 migrations (one of them is 0x...dead).
#
# The measurement that settles it: across all 105 migrations,
# max(TokensSwept / reservedTokenAmountForLP) = 0.999816 and not one
# reaches 1.0. The FLAG band began at 1.0 and the FAIL band at 10.0, so
# both alarms described a state that cannot occur on this chain — yet they
# fired on 422 launches, and were the sole cause of 14 of the 17 FAILs.
#
# Rebuilding it correctly means joining TokensSwept per migration tx,
# reading tokensRecipient(), and recalibrating against the real
# distribution. That is a new check, not a patched threshold, and it does
# not get published until it can be verified the way this one was not.


def derive_assessments(factsheet: dict) -> dict:
    """Fact-determined values and allowed sets for the judge's assessments.

    Same discipline as the verdict ceiling, applied to the classification
    labels: whatever the facts decide, the facts decide — the model does
    not get to relabel a fresh EOA as "established" or an unverified
    ERC20 as "verified_official". Where the facts genuinely run out (the
    economic behavior of a custom hook), the model chooses freely inside
    a bounded set.

    Returns {field: {"fixed": value} | {"allowed": (…)}}.
    """
    p = factsheet["launch"]["params"]
    recipient = factsheet["recipient"]
    currency = factsheet["currency"]

    # Recipient: fully determined by code size and history. The delegation
    # test comes first — an EIP-7702 account has code but is a wallet, and
    # because this value is hard-fixed the judge cannot correct it, so a
    # mislabel here is final.
    if recipient.get("delegated"):
        recipient_rule = {"fixed": "delegated_wallet"}
    elif recipient["code_size"] > 0:
        recipient_rule = {"fixed": "contract"}
    elif recipient["nonce"] == 0:
        recipient_rule = {"fixed": "fresh_eoa"}
    else:
        recipient_rule = {"fixed": "established_eoa"}

    # Hook: "none" is a fact, not an opinion. A nonzero hook is a genuine
    # judgment call, but it can never be called "none".
    if p["pool"]["hook"] == ZERO_ADDRESS:
        hook_rule = {"fixed": "none"}
    else:
        hook_rule = {"allowed": ("benign", "suspicious", "hostile", "unknown")}

    # Currency: native ETH and registry membership are facts. An address
    # in the official RHJ registry is verified; a name that claims the
    # official pattern from an unregistered address is a fixed impostor
    # call, not a matter of opinion. Everything else stays judgmental.
    name = (currency.get("name") or "")
    if currency.get("kind") == "native_eth":
        currency_rule = {"fixed": "native_eth"}
    elif currency.get("official"):
        currency_rule = {"fixed": "verified_official"}
    elif (name.endswith("Robinhood Token")
          and currency.get("registry_status") == registry.NON_MEMBER):
        currency_rule = {"fixed": "likely_impostor"}
    else:
        currency_rule = {"allowed": ("plausible", "unverified",
                                     "likely_impostor", "unknown")}

    return {
        "recipient_assessment": recipient_rule,
        "hook_assessment": hook_rule,
        "currency_assessment": currency_rule,
    }


# Bumped whenever the check set changes in a way that would alter an
# existing row's findings or ceiling. Cached rows carry this stamp; a
# mismatch forces re-derivation, so the record is never a mixture of
# launches judged under different rules.
CHECKS_VERSION = 4


def build_factsheet(rpc: Rpc, launch: dict, current_block: Optional[int] = None) -> dict:
    """All deterministic facts for one InitializerCreated launch record."""
    p = launch["params"]
    findings = []
    findings += check_schedule(p["lpAllocationSchedule"])
    findings += check_positions(p["positionDefinitions"])
    findings += check_pool(p["pool"])

    recipient_facts = gather_address_facts(rpc, p["recipient"])
    findings += check_recipient(recipient_facts)

    currency_facts = check_currency(rpc, p["currency"])
    findings += currency_facts["findings"]

    if current_block is None:
        current_block = rpc.block_number()

    token_supply = rpc.read_uint(p["token"], Rpc.SEL_TOTAL_SUPPLY)
    reserved_ratio = None
    if token_supply:
        reserved_ratio = p["reservedTokenAmountForLP"] / token_supply
        if reserved_ratio < 0.01:
            findings.append((
                "lp_reserve_negligible", FAIL,
                "only %.2f%% of supply is reserved for liquidity, leaving the pool negligible against the rest of the supply"
                % (reserved_ratio * 100),
            ))
        elif reserved_ratio < 0.05:
            findings.append((
                "lp_reserve_thin", FLAG,
                "only %.1f%% of supply is reserved for liquidity" % (reserved_ratio * 100),
            ))


    ceiling = PASS
    for _, severity, _ in findings:
        if affects_ceiling(severity):
            ceiling = worse(ceiling, severity)

    return {
        "launch": launch,
        "recipient": recipient_facts,
        "currency": currency_facts,
        "token_total_supply": token_supply,
        "reserved_lp_ratio": reserved_ratio,
        "current_block": current_block,
        "blocks_until_migration": p["migrationBlock"] - current_block,
        "findings": findings,
        "ceiling": ceiling,
    }
