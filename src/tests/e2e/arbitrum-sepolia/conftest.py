import os
import logging
import pytest
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# constants
RPC = os.environ.get("NETWORK_421614_RPC")
ADDRESS = os.environ.get("ADDRESS")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")

SNX_DEPLOYER_ADDRESS = ""


# fixtures
@pytest.fixture(scope="module")
def snx(pytestconfig):
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=RPC,
        address=ADDRESS,
        private_key=PRIVATE_KEY,
        network_id=421614,
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "latest",
            "preset": "arbthetix",
        },
    )

    return snx


@pytest.fixture(scope="module")
def contracts(pytestconfig, snx):
    # create some needed contracts
    dai = snx.web3.eth.contract(
        address=snx.contracts["packages"]["dai_mock_collateral"]["MintableToken"][
            "address"
        ],
        abi=snx.contracts["packages"]["dai_mock_collateral"]["MintableToken"]["abi"],
    )

    usdc = snx.web3.eth.contract(
        address=snx.contracts["packages"]["usdc_mock_collateral"]["MintableToken"][
            "address"
        ],
        abi=snx.contracts["packages"]["usdc_mock_collateral"]["MintableToken"]["abi"],
    )

    snx = snx.web3.eth.contract(
        address=snx.contracts["packages"]["snx_mock_collateral"]["MintableToken"][
            "address"
        ],
        abi=snx.contracts["packages"]["snx_mock_collateral"]["MintableToken"]["abi"],
    )

    return {
        "dai": dai,
        "usdc": usdc,
        "snx": snx,
    }
