# Trade Perps

This guide will help you get started trading Synthetix Perps. If you complete the steps in this guide you will be able to:
1. Initialize the Synthetix client
1. Create an account
1. Manage your account margin
1. Make trades
1. Monitor your positions

## Setting Up

First, ensure you have the latest version of `synthetix` installed in your environment. Execute the following command in your terminal:

```bash
pip install --upgrade synthetix
```

If you need additional help installing the library, refer to the quickstart guide.

### Initializing the Client

Initialize the client using the following code:

```python
from synthetix import Synthetix

snx = Synthetix(
    provider_rpc="https://base-sepolia.g.alchemy.com/v2/<api key>",
    network_id=84532,
    address="<your address>",
    private_key="<your private key>"
)
```

To avoid storing these secrets directly in your scripts, you can use a `.env` file and the `load_dotenv` library. Install it using the following command:

```bash
pip install python-dotenv
```

Next, create a `.env` file in your project directory and add the following lines:

```
PROVIDER_RPC=https://base-sepolia.g.alchemy.com/v2/<api key>
NETWORK=84532
ADDRESS=<your address>
PRIVATE_KEY=<your private key>
```

Finally, initialize the client with the following code:

```python
import os
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

snx = Synthetix(
    provider_rpc=os.getenv("PROVIDER_RPC"),
    network_id=os.getenv("NETWORK"),
    address=os.getenv("ADDRESS"),
    private_key=os.getenv("PRIVATE_KEY")
)
```

### Creating an Account

To begin, you'll need to create an account. Each perps account is minted as an NFT to your address. The account will be used to track your margin balances and open positions. Here's how you can create an account:

```python
>>> account_tx = snx.perps.create_account(submit=True)
```

The newly created account will be used as the default for all future transactions.

## Managing Account Margin

Before you can make trades, you'll need to deposit collateral into your account. Here's how you can check the current balances in your perps account, and in your wallet:

```python
>>> snx.perps.get_collateral_balances()
{'sUSD': 0.0}

>>> snx.get_susd_balance()
{'balance': 1000.0}
```

In this example you can see the wallet has 1000 sUSD, but the perps account has no collateral balances. Let's deposit 100 sUSD into the account, but first we need to make sure to approve sUSD transfers to the perps contract:

```python
>>> perps_address = snx.perps.market_proxy.address
>>> approve_tx = snx.spot.approve(perps_address, market_name='sUSD', submit=True)
```

Then you can deposit the sUSD into the perps account:

```python
>>> deposit_tx = snx.perps.modify_collateral(100, market_name='sUSD', submit=True)
```

Check your balance again to confirm the successful deposit:

```python
>>> snx.perps.get_collateral_balances()
{'sUSD': 100.0}
```

## Submitting an Order

All trades on Synthetix perps are executed in two steps: first, the user commits an order; then, following a delay, the order is executed. Orders are filled at the price at execution time.

Commit an order:

```python
>>> snx.perps.commit_order(0.1, market_name='ETH', submit=True)
```

After an order is submitted, you can check its status:
```python
>>> order = snx.perps.get_order()
>>> order
{
    'market_id': 100,
    'account_id': 1,
    'commitment_time': 1697215535,
    'size_delta': 0.1,
    'settlement_strategy_id': 1, 
    'acceptable_price': 1533.6071692221237,
    'settlement_strategy': {
        'settlement_delay': 2,
        'commitment_price_delay': 2,
        'settlement_window_duration': 60
    }
    ...
}
```

Note:
* The `commitment_time` represents the unix timestamp when this order is was committed.
* The `settlement_strategy` contains the parameters defining when the order can be executed, and when it expires.
* The order can be settled `settlement_delay` seconds after the order is committed.
* The `size_delta` is set to 0 after the order is executed. If it shows 0, check the position to confirm it was filled.
* You don't need to specify the market name when checking the order status, because accounts are limited to 1 open order at a time.

## Settling an order

In most cases, you should expect an order to be settled by a keeper, who will call `settleOrder` for you. However, if your orders are expiring you can call the function yourself:

```python
settle_tx = snx.perps.settle_order(submit=True)
```

This will print logs as the required price data is fetched in order to settle the order. You can tell an order has settled two ways:
* The `size_delta` on `snx.perps.get_order()` is reset to 0.
* The `position_size` on `snx.perps.get_open_positions()` has updated for the market you are trading.

### Checking Your Position

After an order is executed, you can check your position using `get_open_positions`. This function will fetch all positions with nonzero sizes. If you have no open positions, it will return an empty dictionary:

```python
>>> positions = snx.perps.get_open_positions()
>>> positions
{
    'ETH': {
        'market_id': 100,
        'market_name': 'ETH',
        'pnl': 1.52,
        'accrued_funding': 0.002245,
        'position_size': 0.1
    }
}
```

## Conclusion

Congratulations! You have now mastered the basics of trading Synthetix perps. To see the full API reference for the perps module, check out the full [API Reference](https://synthetixio.github.io/python-sdk/modules/synthetix.html) section of the docs.
