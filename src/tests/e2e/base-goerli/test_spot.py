from pytest import raises
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# tests


def test_spot_module(snx, logger):
    """The instance has a spot module"""
    assert snx.spot is not None
    assert snx.spot.market_proxy is not None
