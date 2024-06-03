# tests


def test_snx(snx):
    """The instance has a Synthetix instance"""
    assert snx is not None


def test_contracts(contracts):
    """The instance has necessary contracts"""
    assert contracts["WETH"] is not None
    assert contracts["USDC"] is not None
    assert contracts["ARB"] is not None


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
