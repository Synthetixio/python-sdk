import pytest
from dotenv import load_dotenv

load_dotenv()

# tests
MARKET_NAMES = ["ETH", "BTC", "SOL", "SNX", "WIF", "W"]
TEST_COLLATERAL_AMOUNT = 1000
TEST_POSITION_SIZE_USD = 500


def test_perps_module(snx, logger):
    """The instance has a perps module"""
    assert snx.perps is not None
    assert snx.perps.market_proxy is not None
    assert snx.perps.account_proxy is not None
    assert snx.perps.account_ids is not None
    assert snx.perps.markets_by_id is not None
    assert snx.perps.markets_by_name is not None


def test_perps_markets(snx, logger):
    markets_by_id, markets_by_name = snx.perps.get_markets()

    logger.info(f"Markets by id: {markets_by_id}")
    logger.info(f"Markets by name: {markets_by_name}")

    assert markets_by_id is not None
    assert markets_by_name is not None

    for market in MARKET_NAMES:
        assert (
            market in markets_by_name
        ), f"Market {market} is missing in markets_by_name"


def test_perps_account_fetch(snx, logger, account_id):
    """The instance can fetch account ids"""
    account_ids = snx.perps.get_account_ids()
    logger.info(
        f"Address: {snx.address} - accounts: {len(account_ids)} - account_ids: {account_ids}"
    )
    assert len(account_ids) > 0
    assert account_id in account_ids


def test_modify_collateral(snx, account_id):
    """Test modify collateral"""
    # get starting collateral and sUSD balance
    margin_info_start = snx.perps.get_margin_info(account_id)
    susd_balance_start = snx.get_susd_balance()

    # check allowance
    allowance = snx.spot.get_allowance(
        snx.perps.market_proxy.address, market_name="sUSD"
    )
    if allowance < TEST_COLLATERAL_AMOUNT:
        approve_tx = snx.spot.approve(
            snx.perps.market_proxy.address, market_name="sUSD", submit=True
        )
        snx.wait(approve_tx)

    # modify collateral
    modify_tx = snx.perps.modify_collateral(
        TEST_COLLATERAL_AMOUNT, market_name="sUSD", account_id=account_id, submit=True
    )
    snx.wait(modify_tx)

    # check the result
    margin_info_end = snx.perps.get_margin_info(account_id)
    susd_balance_end = snx.get_susd_balance()

    assert (
        margin_info_end["total_collateral_value"]
        > margin_info_start["total_collateral_value"]
    )
    assert susd_balance_end["balance"] < susd_balance_start["balance"]
    assert (
        susd_balance_end["balance"]
        == susd_balance_start["balance"] - TEST_COLLATERAL_AMOUNT
    )


@pytest.mark.parametrize(
    "market_name",
    MARKET_NAMES,
)
def test_account_flow(snx, new_account_id, market_name):
    # check allowance
    allowance = snx.spot.get_allowance(
        snx.perps.market_proxy.address, market_name="sUSD"
    )
    if allowance < TEST_COLLATERAL_AMOUNT:
        approve_tx = snx.spot.approve(
            snx.perps.market_proxy.address, market_name="sUSD", submit=True
        )
        snx.wait(approve_tx)

    # deposit collateral
    modify_tx = snx.perps.modify_collateral(
        TEST_COLLATERAL_AMOUNT,
        market_name="sUSD",
        account_id=new_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1

    # check the price
    index_price = snx.perps.markets_by_name[market_name]["index_price"]

    # commit order
    position_size = TEST_POSITION_SIZE_USD / index_price
    commit_tx = snx.perps.commit_order(
        position_size,
        market_name=market_name,
        account_id=new_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt = snx.wait(commit_tx)
    assert commit_receipt["status"] == 1

    # wait for the order settlement
    settle_tx = snx.perps.settle_order(account_id=new_account_id, submit=True)
    settle_receipt = snx.wait(settle_tx)
    assert settle_receipt["status"] == 1

    # check the result
    position = snx.perps.get_open_position(
        market_name=market_name, account_id=new_account_id
    )
    assert round(position["position_size"], 12) == round(position_size, 12)

    # get the position size
    position = snx.perps.get_open_position(
        market_name=market_name, account_id=new_account_id
    )
    size = position["position_size"]

    # commit order
    commit_tx_2 = snx.perps.commit_order(
        -size,
        market_name=market_name,
        account_id=new_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt_2 = snx.wait(commit_tx_2)
    assert commit_receipt_2["status"] == 1

    # wait for the order settlement
    settle_tx_2 = snx.perps.settle_order(account_id=new_account_id, submit=True)
    settle_receipt_2 = snx.wait(settle_tx_2)
    assert settle_receipt_2["status"] == 1

    # check the result
    position = snx.perps.get_open_position(market_name="ETH", account_id=new_account_id)
    assert position["position_size"] == 0


@pytest.mark.parametrize(
    ["market_1", "market_2"],
    [
        ("ETH", "BTC"),
        ("ETH", "SOL"),
        ("SNX", "WIF"),
        ("W", "BTC"),
    ],
)
def test_multiple_positions(snx, new_account_id, market_1, market_2):
    # check allowance
    allowance = snx.spot.get_allowance(
        snx.perps.market_proxy.address, market_name="sUSD"
    )
    if allowance < TEST_COLLATERAL_AMOUNT:
        approve_tx = snx.spot.approve(
            snx.perps.market_proxy.address, market_name="sUSD", submit=True
        )
        snx.wait(approve_tx)

    # deposit collateral
    modify_tx = snx.perps.modify_collateral(
        TEST_COLLATERAL_AMOUNT,
        market_name="sUSD",
        account_id=new_account_id,
        submit=True,
    )
    modify_receipt = snx.wait(modify_tx)
    assert modify_receipt["status"] == 1

    ## order 1
    # check the price
    index_price_1 = snx.perps.markets_by_name[market_1]["index_price"]

    # commit order
    position_size_1 = TEST_POSITION_SIZE_USD / index_price_1
    commit_tx_1 = snx.perps.commit_order(
        position_size_1,
        market_name=market_1,
        account_id=new_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt_1 = snx.wait(commit_tx_1)
    assert commit_receipt_1["status"] == 1

    # wait for the order settlement
    settle_tx_1 = snx.perps.settle_order(account_id=new_account_id, submit=True)
    settle_receipt_1 = snx.wait(settle_tx_1)
    assert settle_receipt_1["status"] == 1

    ## order 2
    # check the price
    index_price_2 = snx.perps.markets_by_name[market_2]["index_price"]

    # commit order
    position_size_2 = TEST_POSITION_SIZE_USD / index_price_2
    commit_tx_2 = snx.perps.commit_order(
        position_size_2,
        market_name=market_2,
        account_id=new_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt_2 = snx.wait(commit_tx_2)
    assert commit_receipt_2["status"] == 1

    # wait for the order settlement
    settle_tx_2 = snx.perps.settle_order(account_id=new_account_id, submit=True)
    settle_receipt_2 = snx.wait(settle_tx_2)
    assert settle_receipt_2["status"] == 1

    # get the position sizes
    positions = snx.perps.get_open_positions(account_id=new_account_id)
    size_1 = positions[market_1]["position_size"]
    size_2 = positions[market_2]["position_size"]
    assert round(size_1, 12) == round(position_size_1, 12)
    assert round(size_2, 12) == round(position_size_2, 12)

    ## order 1
    # commit order
    commit_tx_3 = snx.perps.commit_order(
        -size_1,
        market_name=market_1,
        account_id=new_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt_3 = snx.wait(commit_tx_3)
    assert commit_receipt_3["status"] == 1

    # wait for the order settlement
    settle_tx_3 = snx.perps.settle_order(account_id=new_account_id, submit=True)
    settle_receipt_3 = snx.wait(settle_tx_3)
    assert settle_receipt_3["status"] == 1

    ## order 2
    # commit order
    commit_tx_4 = snx.perps.commit_order(
        -size_2,
        market_name=market_2,
        account_id=new_account_id,
        settlement_strategy_id=0,
        submit=True,
    )
    commit_receipt_4 = snx.wait(commit_tx_4)
    assert commit_receipt_4["status"] == 1

    # wait for the order settlement
    settle_tx_4 = snx.perps.settle_order(account_id=new_account_id, submit=True)
    settle_receipt_4 = snx.wait(settle_tx_4)
    assert settle_receipt_4["status"] == 1

    # check the result
    positions = snx.perps.get_open_positions(account_id=new_account_id)
    assert market_1 not in positions
    assert market_2 not in positions
