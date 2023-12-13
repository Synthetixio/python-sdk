from pytest import raises
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# tests


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

    required_keys = ["ETH", "BTC"]
    for key in required_keys:
        assert key in markets_by_name, f"Key {key} is missing in markets_by_name"


def test_perps_account_fetch(snx, logger, account_id):
    """The instance can fetch account ids"""
    account_ids = snx.perps.get_account_ids()
    logger.info(
        f"Address: {snx.address} - accounts: {len(account_ids)} - account_ids: {account_ids}"
    )
    assert len(account_ids) > 0
    assert account_id in account_ids


def test_modify_collateral(snx, logger, account_id):
    """Test modify collateral"""
    # get starting collateral and sUSD balance
    margin_info_start = snx.perps.get_margin_info(account_id)
    susd_balance_start = snx.get_susd_balance()

    # modify collateral
    modify_tx = snx.perps.modify_collateral(
        100, market_name="sUSD", account_id=account_id, submit=True
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
    assert susd_balance_end["balance"] == susd_balance_start["balance"] - 100


def test_open_position(snx, logger, account_id):
    """Test opening a position"""
    # commit order
    commit_tx = snx.perps.commit_order(
        0.1,
        market_name="ETH",
        account_id=account_id,
        settlement_strategy_id=1,
        submit=True,
    )
    snx.wait(commit_tx)

    # wait for the order settlement
    settle_tx = snx.perps.settle_order(account_id=account_id, submit=True)
    snx.wait(settle_tx)

    # check the result
    position = snx.perps.get_open_position(market_name="ETH", account_id=account_id)
    assert position["position_size"] == 0.1


def test_close_position(snx, logger, account_id):
    """Test closing a position"""
    # get the position size
    position = snx.perps.get_open_position(market_name="ETH", account_id=account_id)
    size = position["position_size"]

    # commit order
    commit_tx = snx.perps.commit_order(
        -size,
        market_name="ETH",
        account_id=account_id,
        settlement_strategy_id=1,
        submit=True,
    )
    snx.wait(commit_tx)

    # wait for the order settlement
    snx.perps.settle_order(account_id=account_id, submit=True)

    # check the result
    position = snx.perps.get_open_position(market_name="ETH", account_id=account_id)
    assert position["position_size"] == 0
