import asyncio
import os
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

TEST_ASSET = 'SOL'
TEST_ACCOUNT = '0x48914229dedd5a9922f44441ffccfc2cb7856ee9'
TEST_MIN_TIMESTAMP = 1680307200
TEST_MAX_TIMESTAMP = 1682899200
TEST_PERIOD = 3600

def check_df(df, unique_column, unique_value=None, min_timestamp=None, max_timestamp=None):
    assert df is not None
    assert df.shape[0] > 0
    assert df[unique_column].nunique() == 1 if unique_value else df[unique_column].nunique() > 1
    if unique_value:
        assert df[unique_column].unique()[0] == unique_value
    if min_timestamp:
        assert df['timestamp'].min() >= min_timestamp
    if max_timestamp:
        assert df['timestamp'].max() <= max_timestamp
    for col in df.columns:
        assert col.islower()

# candles
def test_queries_candles_market(snx, logger):
    """The instance can query candles for a specified market"""
    candles_market = asyncio.run(snx.queries.candles(TEST_ASSET))
    logger.info(f"Asset: {TEST_ASSET} - Candles: {candles_market.shape[0]}")

    check_df(candles_market, 'synth', TEST_ASSET)

def test_queries_candles_period(snx, logger):
    """The instance can query candles for a specified period"""
    candles_market = asyncio.run(snx.queries.candles(TEST_ASSET, period=TEST_PERIOD))
    logger.info(f"Asset: {TEST_ASSET} - Candles: {candles_market.shape[0]}")

    check_df(candles_market, 'period', TEST_PERIOD)

# trades_for_market
def test_queries_trades_all_markets(snx, logger):
    """The instance can query trades for all markets"""
    trades_market = asyncio.run(snx.queries.trades_for_market())
    logger.info(f"Asset: All - Trades: {trades_market.shape[0]}")

    check_df(trades_market, 'asset')

def test_queries_trades_market(snx, logger):
    """The instance can query trades for a specified market"""
    trades_market = asyncio.run(snx.queries.trades_for_market(TEST_ASSET))
    logger.info(f"Asset: {TEST_ASSET} - Trades: {trades_market.shape[0]}")

    check_df(trades_market, 'asset', TEST_ASSET)

def test_queries_trades_market_inputs(snx, logger):
    """The instance can query trades with inputs for a specified market"""
    trades_market = asyncio.run(snx.queries.trades_for_market(TEST_ASSET, min_timestamp=TEST_MIN_TIMESTAMP, max_timestamp=TEST_MAX_TIMESTAMP))
    logger.info(f"Asset: {TEST_ASSET} - Trades: {trades_market.shape[0]}")

    check_df(trades_market, 'asset', TEST_ASSET, TEST_MIN_TIMESTAMP, TEST_MAX_TIMESTAMP)

# trades_for_account
def test_queries_trades_account_internal(snx, logger):
    """The instance can query trades for the connected account"""
    trades_account = asyncio.run(snx.queries.trades_for_account())
    logger.info(f"Account: {snx.address} - Trades: {trades_account.shape[0]}")

    check_df(trades_account, 'account', snx.address.lower())

def test_queries_trades_account_specified(snx, logger):
    """The instance can query trades for a specified account"""
    trades_account = asyncio.run(snx.queries.trades_for_account(TEST_ACCOUNT))
    logger.info(f"Account: {TEST_ACCOUNT} - Trades: {trades_account.shape[0]}")

    check_df(trades_account, 'account', TEST_ACCOUNT)

def test_queries_trades_account_inputs(snx, logger):
    """The instance can query trades with inputs for a specified account"""
    trades_account = asyncio.run(snx.queries.trades_for_account(TEST_ACCOUNT, min_timestamp=TEST_MIN_TIMESTAMP, max_timestamp=TEST_MAX_TIMESTAMP))
    logger.info(f"Account: {TEST_ACCOUNT} - Trades: {trades_account.shape[0]}")

    check_df(trades_account, 'account', TEST_ACCOUNT, TEST_MIN_TIMESTAMP, TEST_MAX_TIMESTAMP)

# transfers_for_market
def test_queries_transfers_all_markets(snx, logger):
    """The instance can query transfers for all markets"""
    transfers_market = asyncio.run(snx.queries.transfers_for_market())
    logger.info(f"Asset: All - Transfers: {transfers_market.shape[0]}")

    check_df(transfers_market, 'asset')

def test_queries_transfers_market(snx, logger):
    """The instance can query transfers for a specified market"""
    transfers_market = asyncio.run(snx.queries.transfers_for_market(TEST_ASSET))
    logger.info(f"Asset: {TEST_ASSET} - Transfers: {transfers_market.shape[0]}")

    check_df(transfers_market, 'asset', TEST_ASSET)

def test_queries_transfers_market_inputs(snx, logger):
    """The instance can query transfers with inputs for a specified market"""
    transfers_market = asyncio.run(snx.queries.transfers_for_market(TEST_ASSET, min_timestamp=TEST_MIN_TIMESTAMP, max_timestamp=TEST_MAX_TIMESTAMP))
    logger.info(f"Asset: {TEST_ASSET} - Transfers: {transfers_market.shape[0]}")

    check_df(transfers_market, 'asset', TEST_ASSET, TEST_MIN_TIMESTAMP, TEST_MAX_TIMESTAMP)

# transfers_for_account
def test_queries_transfers_account_internal(snx, logger):
    """The instance can query transfers for the connected account"""
    transfers_account = asyncio.run(snx.queries.transfers_for_account())
    logger.info(f"Account: {snx.address} - Transfers: {transfers_account.shape[0]}")

    check_df(transfers_account, 'account', snx.address.lower())

def test_queries_transfers_account_specified(snx, logger):
    """The instance can query transfers for a specified account"""
    transfers_account = asyncio.run(snx.queries.transfers_for_account(TEST_ACCOUNT))
    logger.info(f"Account: {TEST_ACCOUNT} - Transfers: {transfers_account.shape[0]}")

    check_df(transfers_account, 'account', TEST_ACCOUNT)

def test_queries_transfers_account_inputs(snx, logger):
    """The instance can query transfers with inputs for a specified account"""
    transfers_account = asyncio.run(snx.queries.transfers_for_account(TEST_ACCOUNT, min_timestamp=TEST_MIN_TIMESTAMP, max_timestamp=TEST_MAX_TIMESTAMP))

    check_df(transfers_account, 'account', TEST_ACCOUNT, TEST_MIN_TIMESTAMP, TEST_MAX_TIMESTAMP)

# positions_for_market
def test_queries_positions_all_markets(snx, logger):
    """The instance can query positions for all markets"""
    positions_market = asyncio.run(snx.queries.positions_for_market())
    logger.info(f"Asset: All - Positions: {positions_market.shape[0]}")

    assert positions_market['is_open'].nunique() == 2
    check_df(positions_market, 'asset')

def test_queries_positions_market(snx, logger):
    """The instance can query positions for a specified market"""
    positions_market = asyncio.run(snx.queries.positions_for_market(TEST_ASSET))
    logger.info(f"Asset: {TEST_ASSET} - Positions: {positions_market.shape[0]}")
    
    assert positions_market['is_open'].nunique() == 2
    check_df(positions_market, 'asset', TEST_ASSET)

def test_queries_positions_market_open(snx, logger):
    """The instance can query positions for a open positions only"""
    positions_market = asyncio.run(snx.queries.positions_for_market(TEST_ASSET, open_only=True))
    logger.info(f"Asset: {TEST_ASSET} - Positions: {positions_market.shape[0]}")

    assert positions_market['is_open'].nunique() == 1
    check_df(positions_market, 'is_open', True)

# positions_for_account
def test_queries_positions_account_internal(snx, logger):
    """The instance can query positions for the connected account"""
    positions_account = asyncio.run(snx.queries.positions_for_account())
    logger.info(f"Account: {snx.address} - Positions: {positions_account.shape[0]}")

    check_df(positions_account, 'account', snx.address.lower())

def test_queries_positions_account_specified(snx, logger):
    """The instance can query positions for a specified account"""
    positions_account = asyncio.run(snx.queries.positions_for_account(TEST_ACCOUNT))
    logger.info(f"Account: {TEST_ACCOUNT} - Positions: {positions_account.shape[0]}")

    check_df(positions_account, 'account', TEST_ACCOUNT)

# funding_rates
def test_queries_funding_rates_all_markets(snx, logger):
    """The instance can query funding rates for all markets"""
    funding_rates_market = asyncio.run(snx.queries.funding_rates())
    logger.info(f"Asset: All - Funding Rates: {funding_rates_market.shape[0]}")

    check_df(funding_rates_market, 'asset')

def test_queries_funding_rates_market(snx, logger):
    """The instance can query funding rates for a specified market"""
    funding_rates_market = asyncio.run(snx.queries.funding_rates(TEST_ASSET))
    logger.info(f"Asset: {TEST_ASSET} - Funding Rates: {funding_rates_market.shape[0]}")

    check_df(funding_rates_market, 'asset', TEST_ASSET)

def test_queries_funding_rates_inputs(snx, logger):
    """The instance can query funding rates with inputs for a specified market"""
    funding_rates_market = asyncio.run(snx.queries.funding_rates(TEST_ASSET, min_timestamp=TEST_MIN_TIMESTAMP, max_timestamp=TEST_MAX_TIMESTAMP))

    check_df(funding_rates_market, 'asset', TEST_ASSET, TEST_MIN_TIMESTAMP, TEST_MAX_TIMESTAMP)
