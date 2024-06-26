# Quickstart

This library offers a way to interact with the [Synthetix](https://synthetix.io/) protocol using Python. This guide will teach you the basics: how to set up the client and use some of its functions.

If your use case requires a more in-depth understanding of the protocol, please refer to the [Synthetix documentation](https://docs.synthetix.io/).

## Requirements

This library requires Python 3.8 or higher. It makes heavy use of the [web3.py](https://github.com/ethereum/web3.py) library for interacting with smart contracts.

It is recommended to use a virtual environment to install the library and its dependencies. Use [venv](https://docs.python.org/3/library/venv.html) to create and manage this virtual environment:

```bash
python3 -m venv env
source env/bin/activate

# optionally upgrade pip
pip install --upgrade pip
```

## Installation

The library is available from the PyPI package repository and can be installed using `pip`:

```bash
pip install synthetix
```

## Initializing the client

To use the library, initialize the `Synthetix` object that can be used to interact with the protocol. At minimum, you must provide an RPC endpoint. 

```python
from synthetix import Synthetix

# Base Mainnet
snx = Synthetix(
    provider_url="https://base.llamarpc.com",
)
```

This creates an `snx` object that helps you interact with the protocol smart contracts. At minimum you need to provide the `provider_url` parameter, which is the RPC endpoint of the node you want to connect to. If there are any warnings or errors during initialization, they are logged to the console.

## Basic usage

Once set up, you can use the `snx` object to interact with the different modules in the protocol. Here are some common functions you may want to use:

```python
# basic functions
snx.get_susd_balance()       # fetch the balance of sUSD
snx.get_eth_balance()        # fetch the balance of ETH and WETH

# perps markets
snx.perps.get_markets()      # fetch all perps market summaries
snx.perps.get_account_ids()  # fetch all perps accounts for the specified address
snx.perps.get_margin_info(1) # get the margin balances for account_id 1
```

Let's see how to use the get_markets function with a sample output:
```python
>>> markets_by_id, markets_by_name = snx.perps.get_markets()
>>> markets_by_name
{
    'ETH': {
        'market_id': 100,
        'market_name': 'ETH',
        'skew': -3308.71,
        'size': 14786.42
        'max_open_interest': 100000,
        'current_funding_rate': 0.00196
        'current_funding_velocity': -0.02977
        'index_price': 1560.37
    },
    'BTC': {
        ...
    },
    ...
}
```
