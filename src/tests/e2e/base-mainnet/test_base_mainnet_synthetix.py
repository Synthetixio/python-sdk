from synthetix.utils import ether_to_wei, wei_to_ether
from dotenv import load_dotenv

load_dotenv()

# tests


def test_snx(snx, logger):
    """The instance has a Synthetix instance"""
    assert snx is not None


def test_wrap_eth(snx):
    """The instance can wrap ETH"""
    tx_hash = snx.wrap_eth(0.01, submit=True)
    tx_receipt = snx.wait(tx_hash)

    assert tx_hash is not None
    assert tx_receipt is not None
    assert tx_receipt.status == 1


def test_unwrap_eth(snx):
    """The instance can unwrap ETH"""
    tx_hash = snx.wrap_eth(-0.01, submit=True)
    tx_receipt = snx.wait(tx_hash)

    assert tx_hash is not None
    assert tx_receipt is not None
    assert tx_receipt.status == 1
