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
    TOPIC_INITIALIZER_CREATED,
    TOPIC_TOKEN_CREATED,
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


def find_launch_logs(receipt: dict, strategy: str) -> List[dict]:
    """Extract InitializerCreated logs emitted by the strategy from a receipt."""
    out = []
    for log in receipt.get("logs", []):
        if (log["address"].lower() == strategy.lower()
                and log["topics"][0].lower() == TOPIC_INITIALIZER_CREATED):
            out.append(decode_initializer_created(log))
    return out
