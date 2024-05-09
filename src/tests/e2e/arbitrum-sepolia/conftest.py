import os
import logging
import pytest
from synthetix import Synthetix
from synthetix.utils import ether_to_wei
from dotenv import load_dotenv

load_dotenv()

# constants
RPC = os.environ.get("LOCAL_RPC")
MAINNET_RPC = os.environ.get("NETWORK_1_RPC")

SNX_DEPLOYER_ADDRESS = "0x48914229deDd5A9922f44441ffCCfC2Cb7856Ee9"
USDC_WHALE = "0x09eF1E9AA278C4A234a897c736fa933E9B2617a7"


# fixtures
@pytest.fixture(scope="module")
def snx(pytestconfig):
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=RPC,
        mainnet_rpc=MAINNET_RPC,
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
def mint_dai(snx, contracts):
    """The instance can mint DAI tokens"""
    snx.web3.provider.make_request("anvil_impersonateAccount", [SNX_DEPLOYER_ADDRESS])

    contract = contracts["DAI"]
    tx_params = contract.functions.mint(
        ether_to_wei(100000), snx.address
    ).build_transaction(
        {
            "from": SNX_DEPLOYER_ADDRESS,
            "nonce": snx.web3.eth.get_transaction_count(SNX_DEPLOYER_ADDRESS),
        }
    )

    # Send the transaction directly without signing
    tx_hash = snx.web3.eth.send_transaction(tx_params)
    receipt = snx.wait(tx_hash)
    if receipt["status"] != 1:
        raise Exception("DAI mint failed")

    assert tx_hash is not None
    assert receipt is not None
    assert receipt.status == 1
    snx.logger.info(f"Minted DAI")


@pytest.fixture(scope="module")
def mint_arb(snx, contracts):
    """The instance can mint ARB tokens"""
    snx.web3.provider.make_request("anvil_impersonateAccount", [SNX_DEPLOYER_ADDRESS])

    contract = contracts["ARB"]
    tx_params = contract.functions.mint(
        ether_to_wei(100000), snx.address
    ).build_transaction(
        {
            "from": SNX_DEPLOYER_ADDRESS,
            "nonce": snx.web3.eth.get_transaction_count(SNX_DEPLOYER_ADDRESS),
        }
    )

    # Send the transaction directly without signing
    tx_hash = snx.web3.eth.send_transaction(tx_params)
    receipt = snx.wait(tx_hash)
    if receipt["status"] != 1:
        raise Exception("ARB mint failed")

    assert tx_hash is not None
    assert receipt is not None
    assert receipt.status == 1
    snx.logger.info(f"Minted ARB")


@pytest.fixture(scope="module")
def steal_usdc(snx, contracts):
    """The instance can steal USDC tokens"""
    # check usdc balance
    usdc_contract = contracts["USDC"]
    usdc_balance = usdc_contract.functions.balanceOf(snx.address).call()
    usdc_balance = usdc_balance / 10**6

    # get some usdc
    if usdc_balance < 100000:
        transfer_amount = int((100000 - usdc_balance) * 10**6)
        snx.web3.provider.make_request("anvil_impersonateAccount", [USDC_WHALE])

        tx_params = usdc_contract.functions.transfer(
            snx.address, transfer_amount
        ).build_transaction(
            {
                "from": USDC_WHALE,
                "nonce": snx.web3.eth.get_transaction_count(USDC_WHALE),
            }
        )

        # Send the transaction directly without signing
        tx_hash = snx.web3.eth.send_transaction(tx_params)
        receipt = snx.wait(tx_hash)
        if receipt["status"] != 1:
            raise Exception("USDC Transfer failed")

        assert tx_hash is not None
        assert receipt is not None
        assert receipt.status == 1
        snx.logger.info(f"Stole USDC from {USDC_WHALE}")


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
