from decimal import Decimal

# default
DEFAULT_NETWORK_ID = 8453
DEFAULT_TRACKING_CODE = (
    "0x53594e5448455449585f53444b00000000000000000000000000000000000000"
)
DEFAULT_REFERRER = "0x0000000000000000000000000000000000000000"
DEFAULT_SLIPPAGE = 2.0
DEFAULT_GAS_MULTIPLIER = 2.0

DEFAULT_GQL_ENDPOINT_PERPS = {
    10: "https://api.thegraph.com/subgraphs/name/kwenta/optimism-perps",
}

DEFAULT_GQL_ENDPOINT_RATES = {
    10: "https://api.thegraph.com/subgraphs/name/kwenta/optimism-latest-rates",
}

DEFAULT_PRICE_SERVICE_ENDPOINT = "https://hermes.pyth.network"

ETH_DECIMAL = Decimal("1e18")
