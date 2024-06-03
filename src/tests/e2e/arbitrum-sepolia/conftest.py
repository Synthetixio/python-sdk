import os
import logging
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei
from dotenv import load_dotenv

load_dotenv()

# constants
RPC = os.environ.get("NETWORK_421614_RPC")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
OP_MAINNET_RPC = os.environ.get("NETWORK_10_RPC")

SNX_DEPLOYER_ADDRESS = "0x48914229deDd5A9922f44441ffCCfC2Cb7856Ee9"
USDC_WHALE = "0x09eF1E9AA278C4A234a897c736fa933E9B2617a7"


# fixtures
@pytest.fixture(scope="module")
def snx(pytestconfig):
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=RPC,
        private_key=PRIVATE_KEY,
        op_mainnet_rpc=OP_MAINNET_RPC,
        cannon_config={
            "package": "synthetix-omnibus",
            "version": "latest",
            "preset": "main",
        },
    )

    return snx


@pytest.fixture(scope="module")
def contracts(snx):
    # create some needed contracts
    weth = snx.contracts["WETH"]["contract"]

    dai = snx.web3.eth.contract(
        address=snx.contracts["packages"]["dai_mock_collateral"]["MintableToken"][
            "address"
        ],
        abi=snx.contracts["packages"]["dai_mock_collateral"]["MintableToken"]["abi"],
    )

    usdc = snx.contracts["USDC"]["contract"]

    arb = snx.web3.eth.contract(
        address=snx.contracts["packages"]["arb_mock_collateral"]["MintableToken"][
            "address"
        ],
        abi=snx.contracts["packages"]["arb_mock_collateral"]["MintableToken"]["abi"],
    )

    return {
        "WETH": weth,
        "DAI": dai,
        "USDC": usdc,
        "ARB": arb,
    }


@pytest.fixture(scope="module")
def wrap_eth(snx):
    """The instance can wrap ETH"""
    # check balance
    eth_balance = snx.get_eth_balance()
    if eth_balance["weth"] < 10:
        tx_hash = snx.wrap_eth(10, submit=True)
        tx_receipt = snx.wait(tx_hash)

        assert tx_hash is not None
        assert tx_receipt is not None
        assert tx_receipt.status == 1
        snx.logger.info(f"Wrapped ETH")


@pytest.fixture(scope="function")
def core_account_id(snx):
    # create a core account
    tx_hash = snx.core.create_account(submit=True)
    tx_receipt = snx.wait(tx_hash)

    assert tx_hash is not None
    assert tx_receipt is not None
    assert tx_receipt.status == 1

    account_id = snx.core.account_ids[-1]
    snx.logger.info(f"Created core account: {account_id}")
    return account_id
