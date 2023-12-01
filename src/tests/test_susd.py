import os
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()


# tests
def test_susd_contract(snx, logger):
    """The instance has an sUSD contract"""
    assert snx.susd_token is not None


def test_susd_legacy_contract(snx, logger):
    """The instance has an sUSD legacy contract"""
    if snx.network_id in [10, 420]:
        assert snx.susd_legacy_token is not None
    else:
        assert snx.susd_legacy_token is None


def test_susd_balance(snx, logger):
    """The instance has an sUSD balance"""
    balance = snx.get_susd_balance()
    logger.info(f"Balance: {balance}")
    assert balance is not None
    assert balance["balance"] >= 0


def test_susd_legacy_balance(snx, logger):
    """The instance has a legacy sUSD balance"""
    balance = snx.get_susd_balance(legacy=True)
    logger.info(f"Balance: {balance}")
    if snx.network_id in [10, 420]:
        assert balance is not None
        assert balance["balance"] >= 0
    else:
        assert balance["balance"] == 0
