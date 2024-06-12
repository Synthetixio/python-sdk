# Oracle Data

Synthetix V3 uses pull oracles from [Pyth](https://pyth.network/) to fetch the latest prices for assets using the [ERC-7412](https://erc7412.vercel.app/) pattern. The SDK helps handle the process of fetching the required price data for you, however this guide will help understand how the process works.

## ERC-7412 Overview

ERC-7412 is a standard that defines how a smart contract can prompt the user to fetch some offchain data and provide it in their transaction. The flow looks like this:
1. The user calls a function on the smart contract (e.g. `getMarketSummary`)
1. The call fails, providing the user with information about what data they need to provide
1. The user fetches the data from an offchain source and creates a multicall transaction: `[fullfillOracleQuery, getMarketSummary]`
1. The call succeeds after updating the oracle data, then calling the smart contract function again

## ERC-7412 in Synthetix

Synthetix V3 uses the ERC-7412 pattern to ensure that transactions only succeed when the contracts have access to price data within a certain tolerance. For example, some view functions require that prices are under 60 minutes old, otherwise they are considered stale. For more critical operations like order settlement on the perps markets, the contracts may require a price for a specific timestamp.

For the best user experience, it is recommended that users fetch this data "optimistically" before calling a smart contract function. This will ensure that the transaction uses the most recent data and avoids running into reverts during transaction simulation. 

## SDK Integration

The `synthetix` library will handle this logic for you, including optimistic fetching of oracle data. When you call a function that is expected to require some oracle data, the SDK will automatically fetch the required data and include it in a multicall. If the contract requires additional oracle data, the ERC-7412 pattern will be used to fetch the data and prepare a transaction.

To better understand this process, we can look at the `snx.perps.get_market_summaries()` function. This function will fetch information about all of the available perps markets, including the open interest, funding rate, price, skew, and more. The function will optimistically fetch prices for all markets before requesting the market summary. You can see this in action by calling the function and inspecting the logs.

```python
>>> _, markets_by_name = snx.perps.get_markets()
2024-05-01 15:55:10,714 - INFO - Fetching Pyth data for 32 markets

>>> print(markets_by_name)
{
    'ETH': {
        'market_id': 100,
        'feed_id': '0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace',
        ...
    },
    'BTC': {
        ...
    },
}
```

As you can see from the logs, the SDK fetched prices for all available markets from a Pyth node before requesting the market summaries.

## Caching Oracle Data

For situations that require fresh prices but not a specific timestamp, the SDK will cache price data and reuse it for subsequent calls. This is useful for reducing the number of calls made to Pyth nodes. There is a "time to live" setting that determines how long the data is cached before it is considered stale. If you want to always fetch fresh data, you can set the `pyth_cache_ttl` setting to `0`. Otherwise, it represents the number of seconds that the data is considered fresh.

```python
>>> snx = Synthetix(
    provider_url=provider_url,
    pyth_cache_ttl=0, # Always fetch fresh data
)

>>> snx = Synthetix(
    provider_url=provider_url,
    pyth_cache_ttl=5, # Cache price data for 5 seconds
)
```
