from synthetix.utils import ether_to_wei, wei_to_ether
from dotenv import load_dotenv

load_dotenv()

# constants
USD_TEST_AMOUNT = 100
WETH_TEST_AMOUNT = 0.01

# tests


def test_core_module(snx, logger):
    """The instance has a core module"""
    assert snx.core is not None
    assert snx.core.core_proxy is not None


def test_deposit_usdc(snx, contracts):
    """The instance can deposit USDC"""
    usdc = contracts["usdc"]

    # approve
    allowance = snx.allowance(usdc.address, snx.core.core_proxy.address)
    if allowance < USD_TEST_AMOUNT:
        approve_core_tx = snx.approve(
            usdc.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the USDC
    deposit_tx_hash = snx.core.deposit(
        usdc.address, USD_TEST_AMOUNT, decimals=6, submit=True
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)

    assert deposit_tx_hash is not None
    assert deposit_tx_receipt is not None
    assert deposit_tx_receipt.status == 1


def test_withdraw_usdc(snx, contracts):
    """The instance can withdraw USDC"""
    usdc = contracts["usdc"]

    # withdraw the USDC
    withdraw_tx_hash = snx.core.withdraw(
        USD_TEST_AMOUNT, token_address=usdc.address, decimals=6, submit=True
    )
    withdraw_tx_receipt = snx.wait(withdraw_tx_hash)

    assert withdraw_tx_hash is not None
    assert withdraw_tx_receipt is not None
    assert withdraw_tx_receipt.status == 1


def test_deposit_dai(snx, contracts):
    """The instance can deposit DAI"""
    dai = contracts["dai"]

    # approve
    allowance = snx.allowance(dai.address, snx.core.core_proxy.address)
    if allowance < USD_TEST_AMOUNT:
        approve_core_tx = snx.approve(
            dai.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the DAI
    deposit_tx_hash = snx.core.deposit(
        dai.address, USD_TEST_AMOUNT, decimals=6, submit=True
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)

    assert deposit_tx_hash is not None
    assert deposit_tx_receipt is not None
    assert deposit_tx_receipt.status == 1


def test_withdraw_dai(snx, contracts):
    """The instance can withdraw DAI"""
    dai = contracts["dai"]

    # withdraw the DAI
    withdraw_tx_hash = snx.core.withdraw(
        USD_TEST_AMOUNT, token_address=dai.address, decimals=6, submit=True
    )
    withdraw_tx_receipt = snx.wait(withdraw_tx_hash)

    assert withdraw_tx_hash is not None
    assert withdraw_tx_receipt is not None
    assert withdraw_tx_receipt.status == 1


def test_deposit_weth(snx):
    """The instance can deposit WETH"""
    weth = snx.contracts["WETH"]["contract"]

    # check balance
    eth_balance = snx.get_eth_balance()
    if eth_balance["weth"] < WETH_TEST_AMOUNT:
        wrap_tx = snx.wrap_eth(WETH_TEST_AMOUNT - eth_balance["weth"], submit=True)
        snx.wait(wrap_tx)

        eth_balance = snx.get_eth_balance()

    assert eth_balance["weth"] >= WETH_TEST_AMOUNT

    # approve
    allowance = snx.allowance(weth.address, snx.core.core_proxy.address)
    if allowance < WETH_TEST_AMOUNT:
        approve_core_tx = snx.approve(
            weth.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the WETH
    deposit_tx_hash = snx.core.deposit(weth.address, WETH_TEST_AMOUNT, submit=True)
    deposit_tx_receipt = snx.wait(deposit_tx_hash)

    assert deposit_tx_hash is not None
    assert deposit_tx_receipt is not None
    assert deposit_tx_receipt.status == 1


def test_withdraw_weth(snx):
    """The instance can withdraw WETH"""
    weth = snx.contracts["WETH"]["contract"]

    # approve
    allowance = snx.allowance(weth.address, snx.core.core_proxy.address)
    if allowance < WETH_TEST_AMOUNT:
        approve_core_tx = snx.approve(
            weth.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the WETH
    withdraw_tx_hash = snx.core.withdraw(
        WETH_TEST_AMOUNT, token_address=weth.address, submit=True
    )
    withdraw_tx_receipt = snx.wait(withdraw_tx_hash)

    assert withdraw_tx_hash is not None
    assert withdraw_tx_receipt is not None
    assert withdraw_tx_receipt.status == 1
