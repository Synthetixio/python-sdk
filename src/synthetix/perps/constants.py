COLLATERALS_BY_ID = {
    420: {
        0: 'sUSD',
        1: 'BTC',
        2: 'ETH',
    },
    84531: {
        0: 'sUSD',
        1: 'BTC',
        2: 'ETH',
        3: 'LINK'
    }
}
COLLATERALS_BY_NAME = {network: {v: k for k, v in COLLATERALS_BY_ID[network].items()} for network in COLLATERALS_BY_ID}

PERPS_MARKETS_BY_ID = {
    420: {
        100: 'ETH',
        200: 'BTC'
    },
    84531: {
        100: 'ETH',
        200: 'BTC',
        300: 'LINK',
        400: 'OP',
        500: 'SNX',
    }
}
PERPS_MARKETS_BY_NAME = {network: {v: k for k, v in PERPS_MARKETS_BY_ID[network].items()} for network in PERPS_MARKETS_BY_ID}
