from pytest import raises
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# tests


def test_spot_module(snx, logger):
    """The instance has an spot module"""
    assert snx.spot is not None
    assert snx.perps.market_proxy is not None


def test_spot_balances(snx, logger):
    """The instance can fetch a synth balance"""
    usd_balance = snx.spot.get_balance(market_name="sUSD")
    usdc_balance = snx.spot.get_balance(market_name="sUSDC")

    logger.info(f"Address: {snx.address} - USD balance: {usd_balance}")
    logger.info(f"Address: {snx.address} - sUSDC balance: {usdc_balance}")
    assert usd_balance is not None
    assert usdc_balance is not None


def test_spot_allowances(snx, logger):
    """The instance can fetch the allowance for a specified address"""
    target_address = snx.perps.market_proxy.address

    usd_allowance = snx.spot.get_allowance(target_address, market_name="sUSD")
    usdc_allowance = snx.spot.get_allowance(target_address, market_name="sUSDC")

    logger.info(f"Address: {snx.address} - USD allowance: {usd_allowance}")
    logger.info(f"Address: {snx.address} - sUSDC allowance: {usdc_allowance}")
    assert usd_allowance is not None
    assert usdc_allowance is not None


def test_spot_approval(snx, logger):
    """The instance can approve a token"""
    approve = snx.spot.approve(
        snx.perps.market_proxy.address,
        market_name="sUSDC",
    )

    logger.info(f"Address: {snx.address} - tx: {approve}")
    assert approve is not None
    assert approve["from"] == snx.address
    assert approve["data"] is not None
