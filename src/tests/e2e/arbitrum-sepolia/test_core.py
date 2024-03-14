from synthetix.utils import ether_to_wei
from dotenv import load_dotenv

load_dotenv()

# tests


def test_snx(snx, logger):
    """The instance has a Synthetix instance"""
    assert snx is not None


def test_contracts(snx, contracts, logger):
    """The instance has necessary contracts"""
    assert contracts["dai"] is not None
    assert contracts["usdc"] is not None
    assert contracts["snx"] is not None


def test_minting(snx, contracts, logger):
    """The instance can mint tokens"""
    mintable_snx = contracts["snx"]

    mint_snx_tx_params = mintable_snx.functions.mint(
        ether_to_wei(1), snx.address
    ).build_transaction(
        {
            "from": snx.address,
            "nonce": snx.web3.eth.get_transaction_count(snx.address),
        }
    )
    snx.logger.info(f"mint_snx_tx_params: {mint_snx_tx_params}")

    tx_hash = snx.execute_transaction(mint_snx_tx_params)
    tx_receipt = snx.wait(tx_hash)

    snx.logger.info(f"tx_receipt: {tx_receipt}")
    assert tx_receipt is not None
