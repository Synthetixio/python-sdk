COLLATERALS_BY_ID = {
    420: {
        0: 'sUSD',
        1: 'BTC',
        2: 'ETH',
    }
}
COLLATERALS_BY_NAME = {network: {v: k for k, v in COLLATERALS_BY_ID[network].items()} for network in COLLATERALS_BY_ID}

PERPS_MARKETS_BY_ID = {
    420: {
        100: 'ETH',
        200: 'BTC'
    }
}
PERPS_MARKETS_BY_NAME = {network: {v: k for k, v in PERPS_MARKETS_BY_ID[network].items()} for network in PERPS_MARKETS_BY_ID}
