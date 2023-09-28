SPOT_MARKETS_BY_ID = {
    420: {
        0: 'sUSD',
        1: 'BTC',
        2: 'ETH'
    },
    84531: {
        0: 'sUSD',
        1: 'BTC',
        2: 'ETH',
        3: 'LINK',
        4: 'OP',
        5: 'SNX'
    }
}
SPOT_MARKETS_BY_NAME = {network: {v: k for k, v in SPOT_MARKETS_BY_ID[network].items()} for network in SPOT_MARKETS_BY_ID}
