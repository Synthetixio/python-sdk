import pytest
from synthetix.utils import ether_to_wei, wei_to_ether
from dotenv import load_dotenv

load_dotenv()

# constants
USD_TEST_AMOUNT = 1000
USD_MINT_AMOUNT = 900

WETH_TEST_AMOUNT = 1
WETH_MINT_AMOUNT = 1000


# tests
def test_core_module(snx, logger):
    """The instance has a core module"""
    assert snx.core is not None
    assert snx.core.core_proxy is not None


@pytest.mark.parametrize(
    "token_name, test_amount, decimals",
    [
        ("usdc", USD_TEST_AMOUNT, 6),
        ("dai", USD_TEST_AMOUNT, 6),
        ("WETH", WETH_TEST_AMOUNT, 18),
    ],
)
def test_deposit(snx, contracts, token_name, test_amount, decimals):
    """The instance can deposit token"""
    if token_name == "WETH":
        token = snx.contracts["WETH"]["contract"]

        # wrap eth if no balance
        token_balance = wei_to_ether(token.functions.balanceOf(snx.address).call())
        if token_balance < test_amount:
            wrap_tx_hash = snx.wrap_eth(test_amount - token_balance, submit=True)
            snx.wait(wrap_tx_hash)
    else:
        token = contracts[token_name]

    # approve
    allowance = snx.allowance(token.address, snx.core.core_proxy.address)
    if allowance < test_amount:
        approve_core_tx = snx.approve(
            token.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the token
    deposit_tx_hash = snx.core.deposit(
        token.address, test_amount, decimals=decimals, submit=True
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)

    assert deposit_tx_hash is not None
    assert deposit_tx_receipt is not None
    assert deposit_tx_receipt.status == 1


@pytest.mark.parametrize(
    "token_name, test_amount, decimals",
    [
        ("usdc", USD_TEST_AMOUNT, 6),
        ("dai", USD_TEST_AMOUNT, 6),
        ("WETH", WETH_TEST_AMOUNT, 18),
    ],
)
def test_withdraw(snx, contracts, token_name, test_amount, decimals):
    """The instance can withdraw token"""
    if token_name == "WETH":
        token = snx.contracts["WETH"]["contract"]
    else:
        token = contracts[token_name]

    # withdraw the token
    withdraw_tx_hash = snx.core.withdraw(
        test_amount, token_address=token.address, decimals=decimals, submit=True
    )
    withdraw_tx_receipt = snx.wait(withdraw_tx_hash)

    assert withdraw_tx_hash is not None
    assert withdraw_tx_receipt is not None
    assert withdraw_tx_receipt.status == 1


def test_account_delegate_weth(snx, core_account_id):
    """The instance can deposit and delegate"""
    token = snx.contracts["WETH"]["contract"]
    test_amount = WETH_TEST_AMOUNT
    mint_amount = WETH_MINT_AMOUNT

    # wrap eth if no balance
    token_balance = wei_to_ether(token.functions.balanceOf(snx.address).call())
    if token_balance < test_amount:
        wrap_tx_hash = snx.wrap_eth(test_amount - token_balance, submit=True)
        snx.wait(wrap_tx_hash)

    # approve
    allowance = snx.allowance(token.address, snx.core.core_proxy.address)
    if allowance < test_amount:
        approve_core_tx = snx.approve(
            token.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the token
    deposit_tx_hash = snx.core.deposit(
        token.address,
        test_amount,
        account_id=core_account_id,
        submit=True,
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)

    assert deposit_tx_hash is not None
    assert deposit_tx_receipt is not None
    assert deposit_tx_receipt.status == 1

    # delegate the collateral
    delegate_tx_hash = snx.core.delegate_collateral(
        token.address,
        test_amount,
        1,
        account_id=core_account_id,
        submit=True,
    )
    delegate_tx_receipt = snx.wait(delegate_tx_hash)

    assert delegate_tx_hash is not None
    assert delegate_tx_receipt is not None
    assert delegate_tx_receipt.status == 1

    # mint sUSD
    mint_tx_hash = snx.core.mint_usd(
        token.address,
        mint_amount,
        1,
        account_id=core_account_id,
        submit=True,
    )

    mint_tx_receipt = snx.wait(mint_tx_hash)

    assert mint_tx_hash is not None
    assert mint_tx_receipt is not None
    assert mint_tx_receipt.status == 1


@pytest.mark.parametrize(
    "token_name, test_amount, mint_amount, decimals",
    [
        ("usdc", USD_TEST_AMOUNT, USD_MINT_AMOUNT, 6),
        ("dai", USD_TEST_AMOUNT, USD_MINT_AMOUNT, 6),
    ],
)
@pytest.mark.skip(reason="Disabling since issuance is disabled")
def test_account_delegate_usd(
    snx, contracts, core_account_id, token_name, test_amount, mint_amount, decimals
):
    """The instance can deposit and delegate"""
    token = contracts[token_name]

    # approve
    allowance = snx.allowance(token.address, snx.core.core_proxy.address)
    if allowance < test_amount:
        approve_core_tx = snx.approve(
            token.address, snx.core.core_proxy.address, submit=True
        )
        snx.wait(approve_core_tx)

    # deposit the token
    deposit_tx_hash = snx.core.deposit(
        token.address,
        test_amount,
        decimals=decimals,
        account_id=core_account_id,
        submit=True,
    )
    deposit_tx_receipt = snx.wait(deposit_tx_hash)

    assert deposit_tx_hash is not None
    assert deposit_tx_receipt is not None
    assert deposit_tx_receipt.status == 1

    # delegate the collateral
    delegate_tx_hash = snx.core.delegate_collateral(
        token.address,
        test_amount,
        1,
        account_id=core_account_id,
        submit=True,
    )
    delegate_tx_receipt = snx.wait(delegate_tx_hash)

    assert delegate_tx_hash is not None
    assert delegate_tx_receipt is not None
    assert delegate_tx_receipt.status == 1

    # mint sUSD
    mint_tx_hash = snx.core.mint_usd(
        token.address,
        mint_amount,
        1,
        account_id=core_account_id,
        submit=True,
    )

    mint_tx_receipt = snx.wait(mint_tx_hash)

    assert mint_tx_hash is not None
    assert mint_tx_receipt is not None
    assert mint_tx_receipt.status == 1
