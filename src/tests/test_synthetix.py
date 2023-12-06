import os
from synthetix import Synthetix

# tests


def test_synthetix_init(snx):
    """The instance is created"""
    assert snx is not None


def test_synthetix_web3(snx, logger):
    """The instance has a functioning web3 provider"""
    block = snx.web3.eth.get_block(block_identifier="latest")
    logger.info(f"Block: {block}")
    assert block is not None
