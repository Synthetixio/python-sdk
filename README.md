[![GitHub](https://img.shields.io/badge/GitHub-Synthetix%20Python%20SDK-blue?logo=github&style=plastic)](https://github.com/synthetixio/python-sdk) [![pypi](https://img.shields.io/badge/pypi-Synthetix%20Python%20SDK-blue?logo=pypi&style=plastic)](https://pypi.org/project/synthetix/) [![Discord](https://img.shields.io/discord/413890591840272394.svg?color=768AD4&label=discord&logo=https%3A%2F%2Fdiscordapp.com%2Fassets%2F8c9701b98ad4372b58f13fd9f65f966e.svg)](https://discord.com/invite/Synthetix) [![Twitter Follow](https://img.shields.io/twitter/follow/synthetix_io.svg?label=synthetix_io&style=social)](https://twitter.com/synthetix_io)

# Synthetix Python SDK

This is a Python SDK designed to help you interact with Synthetix smart contracts and subgraphs. Visit the [documentation](https://synthetixio.github.io/python-sdk/) for more information.

## Features
* Interfaces for all Synthetix V3 contracts
* Simple tools for trading Synthetix perps
* Interfaces for synth swapping and wrapping
* Inferfaces for managing LP positions
* Seamless integration with [Cannon](https://usecannon.com/) for fetching deployments from IPFS

## Installation

To get started, install the `synthetix` library in your Python environment:

```bash
pip install synthetix
```

## Documentation

There are a few guides to help you get started:
* [Getting Started](https://synthetixio.github.io/python-sdk/guides/quickstart.html)
* [Trade Perps](https://synthetixio.github.io/python-sdk/guides/trade_perps.html)

For complete documentation, visit our [documentation site](https://synthetixio.github.io/python-sdk/).

## Development

If you are interested in contributing to the library's development, you can clone the repository and set up the dependencies for editable mode:

```bash
python3 -m venv env
source env/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install -e ./src
```

Using this method, you'll have the package installed in an 'editable mode'. This means you can easily modify the code and test your changes without the hassle of reinstalling the package every time.
