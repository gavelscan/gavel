"""Chain constants for GAVEL — Robinhood Chain (4663) + Uniswap Liquidity Launcher."""

CHAIN_ID = 4663
DEFAULT_RPC = "https://rpc.mainnet.chain.robinhood.com"

# Uniswap Liquidity Launcher deployments on Robinhood Chain
# Source: github.com/Uniswap/liquidity-launcher README (v3.0.0 / v3.1.0),
# bytecode presence verified on-chain 2026-07-31.
LIQUIDITY_LAUNCHER = "0x00004c4ccc709Ef590F7C81102C0689F0263D4e9"
LBP_STRATEGY = "0x05d552391067389EE44fec3924157ed33F976000"
INITIALIZER_HOOK = "0xD462a559337859369EF271814851A18F496ba000"
INITIALIZER_FACTORY = "0x000000001F26a0044BaA66024e7b6599c61963F8"  # LBPStrategy.initializerFactory()
POSITION_MANAGER = "0x58daec3116aae6D93017bAAea7749052E8a04fA7"
POOL_MANAGER = "0x8366a39CC670B4001A1121B8F6A443A643e40951"

# Event topic0 hashes (keccak256 of canonical signatures).
# Verified against live logs: InitializerCreated topic matches
# tx 0x785de68766c44b1945f431b969f5df7d8de2f2e7e01b709f43dc10276b49801f.
TOPIC_TOKEN_CREATED = "0x2e2b3f61b70d2d131b2a807371103cc98d51adcaa5e9a8f9c32658ad8426e74e"
TOPIC_INITIALIZER_CREATED = "0x6d759545eb439f07e70f45431d6339af7a4f1ffef06d43e8ddf47fdb0799708c"
TOPIC_MIGRATED = "0xbcc36534419debbbf0f25857d1fef3e4bbce9527091c805e9a7da93dbfd828f4"
TOPIC_MIGRATION_FAILED = "0x68b0b16b3bdd5fa8045913c6519a56054f9ffabcc9d3ef1d71520fc0b61f1e15"

# ABI type strings (eth_abi canonical tuples)
MIGRATOR_PARAMS_TYPE = (
    "(address,address,uint64,uint128,address,address,"
    "(uint24,int24,address),bytes,bytes)"
)
POSITION_DEFINITIONS_TYPE = "(int24,int24,uint24,address)[]"
LP_ALLOCATION_SCHEDULE_TYPE = "(uint128,uint24)[]"

# Protocol constants mirrored from MigratorParams.sol / v4-core
MAX_BRACKET_RATE = 10_000_000  # 1e7 mps = 100%
MAX_BRACKETS = 32
DYNAMIC_FEE_FLAG = 0x800000
MAX_LP_FEE = 1_000_000  # v4 LPFeeLibrary.MAX_LP_FEE (100% in hundredths of a bip)
MIN_TICK = -887272
MAX_TICK = 887272

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
