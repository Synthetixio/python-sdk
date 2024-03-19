import os
import logging
import pytest
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# constants
RPC = os.environ.get("LOCAL_RPC")
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


@pytest.fixture(scope="function")
def core_account_id(pytestconfig, snx):
    # create a core account
    tx_hash = snx.core.create_account(submit=True)
    tx_receipt = snx.wait(tx_hash)

    assert tx_hash is not None
    assert tx_receipt is not None
    assert tx_receipt.status == 1

    account_id = snx.core.account_ids[-1]
    return account_id
