# Advanced Usage

## Introduction

This guide will help you understand more advanced concepts for interacting with Synthetix V3 using the `synthetix` library. Check the sidebar for the various topics covered in this guide. If you're just getting started, it is recommended to read the [quickstart](quickstart.md) guide first.

## Contracts

The `synthetix` library provides functions with more simple inputs for interacting with Synthetix V3 contracts. However, you can also interact with the contracts directly using the `web3.py` library. This can be useful for more advanced use cases, debugging, or to access functions that haven't been implemented in a module yet.

The `contracts` module stores contract addresses and ABIs:
```python
# look up the PerpsMarketProxy contract
>>> snx.contracts['PerpsMarketProxy']
{
    'address': '0xf53Ca60F031FAf0E347D44FbaA4870da68250c8d',
    'abi': {...},
    'contract': <web3 contract object>
}

# call a function on the contract
>>> perps_market_proxy = snx.contracts['PerpsMarketProxy']['contract']
>>> perps_market_proxy.functions.getMarkets().call()
(100, 200, ...)
```

## Fetching Cannon Deployments

Synthetix manages smart contract deployments using [Cannon](https://usecannon.com/). During the deployment process, new contract ABIs and addresses will be published to Cannon, however the "hard-coded" versions in the `synthetix` library will not be updated. Note that the `synthetix` library only includes the most commonly used contracts. For other contracts, fetch the addresses and ABIs from Cannon. This can be done during initialization by providing a `cannon_config`:
```python
>>> snx = Synthetix(
    provider_url=provider_url,
    cannon_config={
        'package': 'synthetix-omnibus',
        'version': '12',
        'preset': 'andromeda'
    })
```

This will connect to the Cannon registry onchain and IPFS to fetch the contracts for the specified package, version, and preset. You can then access the contracts for all imported packages using the `contracts` attribute:
```python
>>> snx.contracts["packages"].keys()
dict_keys(['perps_gas_oracle_node', 'pyth_erc7412_wrapper', 'system', ...])
```
