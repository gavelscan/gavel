"""Decoders for Liquidity Launcher / LBPStrategy events.

Every decoded field maps 1:1 to a struct field in the audited Uniswap
source (src/libraries/MigratorParams.sol at the deployed commit). If a
log does not decode cleanly we raise — a launch we cannot decode is a
launch we cannot judge (Invariant I5), never one we silently skip fields on.
"""

from typing import List

from eth_abi import decode as abi_decode

from .constants import (
    LP_ALLOCATION_SCHEDULE_TYPE,
    MIGRATOR_PARAMS_TYPE,
    POSITION_DEFINITIONS_TYPE,
    TOPIC_CURRENCY_SWEPT,
    TOPIC_FUNDS_RECOVERED,
    TOPIC_INITIALIZER_CREATED,
    TOPIC_MIGRATED,
    TOPIC_MIGRATION_FAILED,
    TOPIC_TOKEN_CREATED,
    TOPIC_TOKEN_DISTRIBUTED,
    TOPIC_TOKENS_SWEPT,
)


class DecodeError(Exception):
    pass


def _addr_from_topic(topic: str) -> str:
    if len(topic) != 66:
        raise DecodeError("bad topic length: %s" % topic)
    return "0x" + topic[26:]


def decode_token_created(log: dict) -> dict:
    if log["topics"][0].lower() != TOPIC_TOKEN_CREATED:
        raise DecodeError("not a TokenCreated log")
    return {
        "event": "TokenCreated",
        "token": _addr_from_topic(log["topics"][1]),
        "block": int(log["blockNumber"], 16),
        "tx": log["transactionHash"],
    }


def decode_position_definitions(blob: bytes) -> List[dict]:
    (defs,) = abi_decode([POSITION_DEFINITIONS_TYPE], blob)
    return [
        {
            "offsetLower": d[0],
            "offsetUpper": d[1],
            "weight": d[2],
            "overridePositionRecipient": d[3],
        }
        for d in defs
    ]


def decode_lp_allocation_schedule(blob: bytes) -> List[dict]:
    (brackets,) = abi_decode([LP_ALLOCATION_SCHEDULE_TYPE], blob)
    return [{"lowerThreshold": b[0], "rate": b[1]} for b in brackets]


def decode_initializer_created(log: dict) -> dict:
    """Decode InitializerCreated(initializer indexed, MigratorParameters).

    Returns the full launch record: who gets the money on every path,
    what pool is committed, and the LP plan.
    """
    if log["topics"][0].lower() != TOPIC_INITIALIZER_CREATED:
        raise DecodeError("not an InitializerCreated log")

    data = bytes.fromhex(log["data"][2:])
    (params,) = abi_decode([MIGRATOR_PARAMS_TYPE], data)
    (token, currency, migration_block, reserved_lp, recipient,
     position_recipient, pool_params, position_defs_blob, schedule_blob) = params

    return {
        "event": "InitializerCreated",
        "initializer": _addr_from_topic(log["topics"][1]),
        "block": int(log["blockNumber"], 16),
        "tx": log["transactionHash"],
        "params": {
            "token": token,
            "currency": currency,
            "migrationBlock": migration_block,
            "reservedTokenAmountForLP": reserved_lp,
            "recipient": recipient,
            "positionRecipient": position_recipient,
            "pool": {
                "fee": pool_params[0],
                "tickSpacing": pool_params[1],
                "hook": pool_params[2],
            },
            "positionDefinitions": decode_position_definitions(position_defs_blob),
            "lpAllocationSchedule": decode_lp_allocation_schedule(schedule_blob),
        },
    }


def decode_migrated(log: dict) -> dict:
    """Migrated(initializer indexed, PoolKey indexed, sqrtPrice, plan).

    The PoolKey is indexed, so only its hash survives in topics; the
    concrete pool must be recovered from pool-manager state, not this log.
    """
    if log["topics"][0].lower() != TOPIC_MIGRATED:
        raise DecodeError("not a Migrated log")
    data = bytes.fromhex(log["data"][2:])
    sqrt_price, plan = abi_decode(["uint160", "bytes"], data)
    return {
        "event": "Migrated",
        "initializer": _addr_from_topic(log["topics"][1]),
        "poolKeyHash": log["topics"][2],
        "initialSqrtPriceX96": sqrt_price,
        "planSize": len(plan),
        "block": int(log["blockNumber"], 16),
        "tx": log["transactionHash"],
    }


def decode_migration_failed(log: dict) -> dict:
    if log["topics"][0].lower() != TOPIC_MIGRATION_FAILED:
        raise DecodeError("not a MigrationFailed log")
    data = bytes.fromhex(log["data"][2:])
    (reason,) = abi_decode(["bytes"], data)
    return {
        "event": "MigrationFailed",
        "initializer": _addr_from_topic(log["topics"][1]),
        "reason": "0x" + reason.hex(),
        "block": int(log["blockNumber"], 16),
        "tx": log["transactionHash"],
    }


def _decode_indexed_amount(log: dict, topic: str, event: str,
                           indexed_names: List[str]) -> dict:
    """Shared shape for events with indexed addresses + one uint256 amount."""
    if log["topics"][0].lower() != topic:
        raise DecodeError("not a %s log" % event)
    rec = {
        "event": event,
        "amount": int(log["data"], 16),
        "block": int(log["blockNumber"], 16),
        "tx": log["transactionHash"],
    }
    for i, name in enumerate(indexed_names, start=1):
        rec[name] = _addr_from_topic(log["topics"][i])
    return rec


def decode_token_distributed(log: dict) -> dict:
    return _decode_indexed_amount(log, TOPIC_TOKEN_DISTRIBUTED,
                                  "TokenDistributed", ["token", "strategy"])


def decode_currency_swept(log: dict) -> dict:
    return _decode_indexed_amount(log, TOPIC_CURRENCY_SWEPT,
                                  "CurrencySwept", ["recipient"])


def decode_tokens_swept(log: dict) -> dict:
    return _decode_indexed_amount(log, TOPIC_TOKENS_SWEPT,
                                  "TokensSwept", ["recipient"])


def decode_funds_recovered(log: dict) -> dict:
    return _decode_indexed_amount(log, TOPIC_FUNDS_RECOVERED,
                                  "FundsRecovered", ["initializer", "recipient"])


_DECODERS = {
    TOPIC_TOKEN_CREATED: decode_token_created,
    TOPIC_INITIALIZER_CREATED: decode_initializer_created,
    TOPIC_MIGRATED: decode_migrated,
    TOPIC_MIGRATION_FAILED: decode_migration_failed,
    TOPIC_TOKEN_DISTRIBUTED: decode_token_distributed,
    TOPIC_CURRENCY_SWEPT: decode_currency_swept,
    TOPIC_TOKENS_SWEPT: decode_tokens_swept,
    TOPIC_FUNDS_RECOVERED: decode_funds_recovered,
}


def decode_any(log: dict) -> dict:
    """Total dispatch on topic0 — never raises for a well-formed log dict.

    Unknown topics from watched contracts are surfaced as raw records:
    new event types mean the protocol moved and we must look, not that we
    may ignore (see THREAT_MODEL: upgrades). A known topic whose payload
    no longer decodes (contract upgrade, truncated node response) becomes
    a DecodeFailed record for the same reason — an operator signal in the
    archive, not a silent skip and not a permanent pipeline stall. The
    judge layer never judges Unknown/DecodeFailed records (Invariant I4).
    """
    base = {
        "topic0": log["topics"][0],
        "address": log["address"],
        "block": int(log["blockNumber"], 16),
        "tx": log["transactionHash"],
    }
    decoder = _DECODERS.get(log["topics"][0].lower())
    if decoder is None:
        base["event"] = "Unknown"
        return base
    try:
        return decoder(log)
    except Exception as e:  # DecodeError, eth_abi errors, ValueError
        base["event"] = "DecodeFailed"
        base["error"] = "%s: %s" % (type(e).__name__, e)
        return base


def find_launch_logs(receipt: dict, strategy: str) -> List[dict]:
    """Extract InitializerCreated logs emitted by the strategy from a receipt."""
    out = []
    for log in receipt.get("logs", []):
        if (log["address"].lower() == strategy.lower()
                and log["topics"][0].lower() == TOPIC_INITIALIZER_CREATED):
            out.append(decode_initializer_created(log))
    return out
