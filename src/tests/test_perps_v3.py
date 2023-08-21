from pytest import raises
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# constants
TEST_MARKET_ID = 100
TEST_SETTLEMENT_STRATEGY_ID = 0

# tests


def test_perps_module(snx, logger):
    """The instance has an perps_module"""
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


def test_perps_account_fetch(snx, logger):
    """The instance can fetch account ids"""
    account_ids = snx.perps.get_account_ids()
    logger.info(
        f"Address: {snx.address} - accounts: {len(account_ids)} - account_ids: {account_ids}")
    assert len(account_ids) > 0


def test_perps_account_create(snx, logger):
    """The instance can create perps accounts"""
    create_account = snx.perps.create_account()

    logger.info(f"Address: {snx.address} - tx: {create_account}")
    assert create_account is not None


def test_perps_account_margin_info(snx, logger):
    """The instance can fetch margin balances and requirements for an account"""
    margin_info = snx.perps.get_margin_info()

    logger.info(f"Address: {snx.address} - margin info: {margin_info}")
    assert margin_info is not None
    assert margin_info['total_collateral_value'] is not None
    assert margin_info['available_margin'] is not None
    assert margin_info['withdrawable_margin'] is not None
    assert margin_info['initial_margin_requirement'] is not None
    assert margin_info['maintenance_margin_requirement'] is not None


def test_perps_open_position(snx, logger):
    """The instance can fetch the open position for an account"""
    position = snx.perps.get_open_position(100)

    logger.info(f"Address: {snx.address} - position: {position}")
    assert position is not None
    assert position['pnl'] is not None
    assert position['accrued_funding'] is not None
    assert position['position_size'] is not None


def test_perps_account_collateral_balances(snx, logger):
    """The instance can fetch collateral balances for an account"""
    balances = snx.perps.get_collateral_balances()

    logger.info(f"Address: {snx.address} - balances: {balances}")
    assert balances is not None
    assert balances['sUSD'] is not None
    assert balances['ETH'] is not None
    assert balances['BTC'] is not None


def test_perps_market_summary(snx, logger):
    """The instance can fetch a market summary"""
    market_summary = snx.perps.get_market_summary(TEST_MARKET_ID)

    logger.info(f"Market: {TEST_MARKET_ID} - summary: {market_summary}")
    assert market_summary is not None
    assert market_summary['skew'] is not None
    assert market_summary['size'] is not None
    assert market_summary['max_open_interest'] is not None
    assert market_summary['current_funding_rate'] is not None
    assert market_summary['current_funding_velocity'] is not None
    assert market_summary['index_price'] is not None


def test_perps_settlement_strategy(snx, logger):
    """The instance can fetch a settlement strategy"""
    settlement_strategy = snx.perps.get_settlement_strategy(
        TEST_SETTLEMENT_STRATEGY_ID, TEST_MARKET_ID)

    logger.info(
        f"id: {TEST_SETTLEMENT_STRATEGY_ID} - settlement strategy: {settlement_strategy}")
    assert settlement_strategy is not None
    assert settlement_strategy['strategy_type'] is not None
    assert settlement_strategy['settlement_delay'] is not None
    assert settlement_strategy['settlement_window_duration'] is not None
    assert settlement_strategy['price_window_duration'] is not None
    assert settlement_strategy['price_verification_contract'] is not None
    assert settlement_strategy['feed_id'] is not None
    assert settlement_strategy['url'] is not None
    assert settlement_strategy['settlement_reward'] is not None
    assert settlement_strategy['price_deviation_tolerance'] is not None
    assert settlement_strategy['disabled'] is not None


def test_perps_order(snx, logger):
    """The instance can fetch an order for an account"""
    order = snx.perps.get_order(fetch_settlement_strategy=False)

    logger.info(f"Address: {snx.address} - order: {order}")
    assert order is not None
    assert order['settlement_time'] is not None
    assert order['market_id'] is not None
    assert order['account_id'] is not None
    assert order['size_delta'] is not None
    assert order['settlement_strategy_id'] is not None
    assert order['acceptable_price'] is not None
    assert order['tracking_code'] is not None
    assert order['referrer'] is not None
    assert 'settlement_strategy' not in order


def test_perps_order_with_settlement_strategy(snx, logger):
    """The instance can fetch an order for an account including the settlement strategy"""
    order = snx.perps.get_order()

    logger.info(f"Address: {snx.address} - order: {order}")
    assert order is not None
    assert order['settlement_time'] is not None
    assert order['market_id'] is not None
    assert order['account_id'] is not None
    assert order['size_delta'] is not None
    assert order['settlement_strategy_id'] is not None
    assert order['acceptable_price'] is not None
    assert order['tracking_code'] is not None
    assert order['referrer'] is not None
    assert order['settlement_strategy'] is not None
    assert order['settlement_strategy']['strategy_type'] is not None
    assert order['settlement_strategy']['settlement_delay'] is not None
    assert order['settlement_strategy']['settlement_window_duration'] is not None
    assert order['settlement_strategy']['price_window_duration'] is not None
    assert order['settlement_strategy']['price_verification_contract'] is not None
    assert order['settlement_strategy']['feed_id'] is not None
    assert order['settlement_strategy']['url'] is not None
    assert order['settlement_strategy']['settlement_reward'] is not None
    assert order['settlement_strategy']['price_deviation_tolerance'] is not None
    assert order['settlement_strategy']['disabled'] is not None


def test_perps_modify_collateral(snx, logger):
    """Users can deposit and withdraw collateral"""
    with raises(ValueError):
        # bad market name
        snx.perps.modify_collateral(1, market_name='WRONG')

    with raises(ValueError):
        # bad market id
        snx.perps.modify_collateral(1, market_id=123)

    deposit_tx = snx.perps.modify_collateral(1, market_name='sUSD')
    logger.info(f"Address: {snx.address} - deposit: {deposit_tx}")

    assert deposit_tx is not None


def test_perps_commit_order(snx, logger):
    """User can prepare a commit order transaction"""
    order = snx.perps.commit_order(1, market_name='ETH')

    assert order is not None
    assert order['from'] == snx.address
    assert order['data'] is not None


def test_perps_settle(snx, logger):
    """User can prepare a settlement transaction"""
    settle = snx.perps.settle()

    assert settle is not None
    assert settle['from'] == snx.address
    assert settle['data'] is not None


def test_perps_settle_pyth_order(snx, logger):
    """User can prepare a settlement transaction using Pyth"""
    settle = snx.perps.settle_pyth_order()

    assert settle is not None
    assert settle['from'] == snx.address
    assert settle['data'] is not None
