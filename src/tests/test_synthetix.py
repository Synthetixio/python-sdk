import os
from synthetix import Synthetix

# tests


def test_synthetix_init(snx):
    """The instance is created"""
    assert snx is not None


def test_synthetix_v2_markets(snx, logger):
    """The instance has markets"""
    logger.info(
        f"{len(snx.v2_markets.keys())} Markets: {snx.v2_markets.keys()}")
    assert len(snx.v2_markets) > 0


def test_synthetix_web3(snx, logger):
    """The instance has a functioning web3 provider"""
    block = snx.web3.eth.get_block(block_identifier='latest')
    logger.info(f"Block: {block}")
    assert block is not None
