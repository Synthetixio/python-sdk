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

    required_keys = ['ETH', 'BTC', 'LTC', 'XRP']
    for key in required_keys:
        assert key in markets_by_name, f"Key {key} is missing in markets_by_name"


def test_perps_account_fetch(snx, logger, account_id):
    """The instance can fetch account ids"""
    account_ids = snx.perps.get_account_ids()
    logger.info(
        f"Address: {snx.address} - accounts: {len(account_ids)} - account_ids: {account_ids}")
    assert len(account_ids) > 0
    assert account_id in account_ids

def test_modify_collateral(snx, logger, account_id):
    """Test modify collateral"""
    # get starting collateral and sUSD balance
    margin_info_start = snx.perps.get_margin_info(account_id)
    susd_balance_start = snx.get_susd_balance()

    # modify collateral
    modify_tx = snx.perps.modify_collateral(100, market_name='sUSD', account_id=account_id, submit=True)
    snx.wait(modify_tx)
    
    # check the result
    margin_info_end = snx.perps.get_margin_info(account_id)
    susd_balance_end = snx.get_susd_balance()
    
    assert margin_info_end['total_collateral_value'] > margin_info_start['total_collateral_value']
    assert susd_balance_end['balance'] < susd_balance_start['balance']
    assert susd_balance_end['balance'] == susd_balance_start['balance'] - 100

def test_open_position(snx, logger, account_id):
    """Test modify collateral"""
    # get starting collateral and sUSD balance
    margin_info_start = snx.perps.get_margin_info(account_id)
    susd_balance_start = snx.get_susd_balance()

    # modify collateral
    modify_tx = snx.perps.modify_collateral(100, market_name='sUSD', account_id=account_id, submit=True)
    snx.wait(modify_tx)
    
    # check the result
    margin_info_end = snx.perps.get_margin_info(account_id)
    susd_balance_end = snx.get_susd_balance()
    
    assert margin_info_end['total_collateral_value'] > margin_info_start['total_collateral_value']
    assert susd_balance_end['balance'] < susd_balance_start['balance']
    assert susd_balance_end['balance'] == susd_balance_start['balance'] - 100

