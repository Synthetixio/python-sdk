# Advanced Perps Trading

## Introduction

This guide will help you understand more advanced concepts related to trading Synthetix Perps using the `synthetix` library. Check the sidebar for the various topics covered in this guide. If you're just getting started, it is recommended to read the [Trade Perps](trade_perps.md) guide first.

## Managing Multiple Accounts

Synthetix V3 allows you to hold multiple accounts which each maintain their own balances and positions. Since all positions inside an account use the same collateral, it can be useful to manage multiple accounts to separate different trading strategies or risk profiles. A trader can even simulate "isolated margin" by using separate accounts for each position.

Your accounts are stored in the `account_ids` attribute, and can be refreshed using `get_accounts()`.
```python
# view all accounts
print(snx.perps.account_ids)

# refresh accounts
snx.perps.get_accounts()

# create an account
snx.perps.create_account(submit=True)
```

The default account is set at `snx.perps.default_account_id`. If no account is specified during some function calls, the default account will be used.
```python
>>> print(snx.perps.account_ids)
[1, 2]

>>> print(snx.perps.default_account_id)
1

>>> snx.perps.get_margin_info()             # this will use account 1
>>> snx.perps.get_margin_info(account_id=2) # this will use account 2
```

To replicate isolated margin, you can use separate accounts for each position. This way, the margin and pnl of each position are isolated from each other. In this example, we will deposit 500 snxUSD to account 1 and 2, and open a position on different markets using different accounts. If one position fails to meet the margin requirements and gets liquidated, the other position will not be affected.
```python
snx.perps.modify_collateral(500, account_id=1, submit=True)
snx.perps.modify_collateral(500, account_id=2, submit=True)

snx.perps.commit_order(1, market_name="ETH", account_id=1, submit=True)
snx.perps.commit_order(0.1, market_name="BTC", account_id=2, submit=True)
```

## Fetching Order Quotes

Synthetix perps using a vAMM model, where orders are subject to price impact based on the size of the order. A premium or discount is applied to the index price based on the current skew of the market. For example, if a market is skewed long, there will be a premium applied to the index price, and vice versa.

When placing an order, you can fetch a quote to see the estimated fill price of the order. This fill price is an estimate based on the current index price, current skew, and the size of the order. The quote will also show exchange and settlement fees, and the estimated margin required for a position of that size.
```python
>>> snx.perps.get_quote(1, market_name="ETH")
{
    'order_size': 1,
    'index_price': 2995.72,
    'fill_price': 2995.75,
    'required_margin': 116.49,
    'order_fees': 0.11649,
    'settlement_reward_cost': 1.00137346
}
```

## Liquidations

Liquidations occur when an account fails to meet the margin requirements given the size of their positions. When an account is liquidated, their positions are all closed and their collateral is lost. Liquidations will usually be triggered by keepers who are incentivized to liquidate accounts that fall below the maintenance margin requirement. You can check your margin balance and requirements using `get_margin_info()`.
```python
>>> snx.perps.get_margin_info()
{
    'total_collateral_value': 98.38,
    'available_margin': 98.39,
    'withdrawable_margin': 12.804,
    'initial_margin_requirement': 85.59,
    'maintenance_margin_requirement': 64.02,
    'max_liquidation_reward': 5.634
}
```

If your `available_margin` falls below the `maintenance_margin_requirement`, your account is at risk of liquidation. You can also check the status of an account using `can_liquidate` and `can_liquidates`.
```python
>>> snx.perps.can_liquidate(1)
False

>>> snx.perps.can_liquidates([1, 2])
[(1, False), (2, False)]
```

## Order Settlement

Orders are usually settled onchain by a keeper, but you can also ensure your orders are settled by calling `settle_order`. This will check your order and settle it if it is ready to be settled. This function checks the order status before submission, so if an order has been settled by someone else, it will log this and not attempt to settle the order.

```python
>>> snx.perps.settle_order() # settle order for the default account
INFO     synthetix.synthetix:perps.py:1038 Waiting 0.3958 seconds to settle order
INFO     synthetix.synthetix:pyth.py:99 Fetching Pyth data for 1 markets
INFO     synthetix.synthetix:perps.py:1064 Settling order for account 1701411834604692328273631687329873105994
INFO     synthetix.synthetix:perps.py:1065 settle tx: 0xB9153dbd4160f48f3259d0567fd75508afe8fcaa53ff328313a9654f10182742
INFO     synthetix.synthetix:perps.py:1073 Order settlement successful for account 1701411834604692328273631687329873105994

>>> snx.perps.settle_order() # keeper settles order
INFO     synthetix.synthetix:perps.py:1038 Order is ready to be settled
INFO     synthetix.synthetix:pyth.py:99 Fetching Pyth data for 1 markets
INFO     synthetix.synthetix:perps.py:1064 Settling order for account 1701411834604692328273631687329873105994
INFO     synthetix.synthetix:perps.py:1073 Keeper settled ETH order committed by 1701411834604692328273631687329873105994

>>> snx.perps.settle_order(max_tx_tries=10, tx_delay=5) # increase retries and delay
```

Keep in mind the following:
- In some cases a decentralized keeper will submit their transaction in the same block as you. If this happens, your transaction will fail but your order will be settled.
- You may see some `ERROR` logs during order settlement. Since the order requires data from an offchain provider, sometimes this data is not available in time for the transaction to be submitted. This is normal and the order will be retried. You can use the `max_tx_tries` and `tx_delay` parameters to increase the number of retries and delay between retries.
- Orders expire after a specified duration. The function will throw an error if an order is part the expiration, or if the order has already been settled.
