from pytest import raises
from synthetix import Synthetix
from synthetix.utils import wei_to_ether, format_ether, format_wei
from dotenv import load_dotenv

load_dotenv()

# tests
TEST_AMOUNT = 100


def test_spot_module(snx, logger):
    """The instance has a spot module"""
    assert snx.spot is not None
    assert snx.spot.market_proxy is not None


def test_spot_markets(snx, logger):
    """The instance has an sUSDC market"""
    assert "sUSDC" in snx.spot.markets_by_name
    assert snx.spot.markets_by_name["sUSDC"]["contract"] is not None


def test_spot_wrap(snx, logger):
    """The instance can wrap USDC for sUSDC"""
    usdc = snx.contracts["USDC"]["contract"]

    # make sure we have some USDC
    balance_wei = usdc.functions.balanceOf(snx.address).call()
    balance = format_wei(balance_wei, 6)

    synth_balance = snx.spot.get_balance(market_name="sUSDC")

    assert balance > 0

    # check the allowance
    allowance = snx.allowance(usdc.address, snx.spot.market_proxy.address)

    if allowance < TEST_AMOUNT:
        # approve
        approve_tx = snx.approve(
            usdc.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # wrap
    wrap_tx = snx.spot.wrap(TEST_AMOUNT, market_name="sUSDC", submit=True)
    snx.wait(wrap_tx)

    # get new balances
    new_balance_wei = usdc.functions.balanceOf(snx.address).call()
    new_balance = format_wei(new_balance_wei, 6)

    new_synth_balance = snx.spot.get_balance(market_name="sUSDC")

    assert new_balance == balance - TEST_AMOUNT
    assert new_synth_balance == synth_balance + TEST_AMOUNT


def test_spot_unwrap(snx, logger):
    """The instance can unwrap sUSDC for USDC"""
    usdc = snx.contracts["USDC"]["contract"]
    susdc = snx.spot.markets_by_name["sUSDC"]["contract"]

    # check balances
    balance_wei = usdc.functions.balanceOf(snx.address).call()
    balance = format_wei(balance_wei, 6)

    synth_balance = snx.spot.get_balance(market_name="sUSDC")

    assert synth_balance >= TEST_AMOUNT

    # check the allowance
    allowance = snx.allowance(susdc.address, snx.spot.market_proxy.address)

    if allowance < TEST_AMOUNT:
        # approve
        approve_tx = snx.approve(
            susdc.address, snx.spot.market_proxy.address, submit=True
        )
        snx.logger.info(approve_tx)
        snx.wait(approve_tx)

    # wrap
    wrap_tx = snx.spot.wrap(-TEST_AMOUNT, market_name="sUSDC", submit=True)
    snx.wait(wrap_tx)

    # get new balances
    new_balance_wei = usdc.functions.balanceOf(snx.address).call()
    new_balance = format_wei(new_balance_wei, 6)

    new_synth_balance = snx.spot.get_balance(market_name="sUSDC")

    assert new_balance == balance + TEST_AMOUNT
    assert new_synth_balance == synth_balance - TEST_AMOUNT


def test_spot_atomic_sell(snx, logger):
    """The instance can wrap USDC for sUSDC and sell for sUSD"""
    usdc = snx.contracts["USDC"]["contract"]
    susdc = snx.spot.markets_by_name["sUSDC"]["contract"]

    # make sure we have some USDC
    usdc_balance_wei = usdc.functions.balanceOf(snx.address).call()
    usdc_balance = format_wei(usdc_balance_wei, 6)

    susdc_balance = snx.spot.get_balance(market_name="sUSDC")
    susd_balance = snx.spot.get_balance(market_name="sUSD")
    assert usdc_balance >= TEST_AMOUNT

    # check the allowances
    usdc_allowance = snx.allowance(usdc.address, snx.spot.market_proxy.address)
    susdc_allowance = snx.allowance(susdc.address, snx.spot.market_proxy.address)

    if usdc_allowance < TEST_AMOUNT:
        # approve USDC
        approve_tx = snx.approve(
            usdc.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)
    if susdc_allowance < TEST_AMOUNT:
        # approve sUSDC
        approve_tx = snx.approve(
            susdc.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # wrap
    wrap_tx = snx.spot.wrap(TEST_AMOUNT, market_name="sUSDC", submit=True)
    snx.wait(wrap_tx)

    # sell for sUSD
    sell_tx = snx.spot.atomic_order(
        "sell", TEST_AMOUNT, market_name="sUSDC", submit=True
    )
    snx.wait(sell_tx)

    # get new balances
    new_usdc_balance_wei = usdc.functions.balanceOf(snx.address).call()
    new_usdc_balance = format_wei(new_usdc_balance_wei, 6)

    new_susdc_balance = snx.spot.get_balance(market_name="sUSDC")
    new_susd_balance = snx.spot.get_balance(market_name="sUSD")

    assert new_susd_balance == susd_balance + TEST_AMOUNT
    assert new_usdc_balance == usdc_balance - TEST_AMOUNT
    assert new_susdc_balance == susdc_balance


def test_spot_atomic_buy(snx, logger):
    """The instance can buy sUSDC for sUSD"""
    susd = snx.spot.markets_by_name["sUSD"]["contract"]

    susd_balance = snx.spot.get_balance(market_name="sUSD")
    susdc_balance = snx.spot.get_balance(market_name="sUSDC")
    assert susd_balance >= TEST_AMOUNT

    # check the allowances
    susd_allowance = snx.allowance(susd.address, snx.spot.market_proxy.address)
    if susd_allowance < TEST_AMOUNT:
        # approve sUSDC
        approve_tx = snx.approve(
            susd.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # buy sUSDC
    buy_tx = snx.spot.atomic_order("buy", TEST_AMOUNT, market_name="sUSDC", submit=True)
    snx.wait(buy_tx)

    # get new balances
    new_susdc_balance = snx.spot.get_balance(market_name="sUSDC")
    new_susd_balance = snx.spot.get_balance(market_name="sUSD")

    assert new_susd_balance == susd_balance - TEST_AMOUNT
    assert new_susdc_balance == susdc_balance + TEST_AMOUNT
