import time

# constants
TEST_SYMBOLS = ["ETH", "BTC", "WIF", "SNX"]
TEST_LOOKBACK_SECONDS = 60


def test_pyth(snx):
    assert snx.pyth._price_service_endpoint is not None
    assert snx.pyth.price_feed_ids is not None
    assert snx.pyth.symbol_lookup is not None


def test_pyth_get_price_from_ids(snx, feed_ids):
    query_feed_ids = [feed_ids[symbol] for symbol in TEST_SYMBOLS]

    latest_prices = snx.pyth.get_price_from_ids(query_feed_ids)
    assert latest_prices is not None
    assert latest_prices["price_update_data"] is not None
    assert type(latest_prices["meta"]) == dict

    all_symbols = [meta["symbol"] for meta in latest_prices["meta"].values()]
    assert all([feed_id in latest_prices["meta"] for feed_id in query_feed_ids])
    assert all([symbol in all_symbols for symbol in TEST_SYMBOLS])


def test_pyth_get_price_from_ids_with_timestamp(snx, feed_ids):
    # get timestamp
    publish_time = int(time.time()) - TEST_LOOKBACK_SECONDS

    # look up feed ids
    query_feed_ids = [feed_ids[symbol] for symbol in TEST_SYMBOLS]

    latest_prices = snx.pyth.get_price_from_ids(
        query_feed_ids, publish_time=publish_time
    )
    assert latest_prices is not None
    assert latest_prices["price_update_data"] is not None
    assert type(latest_prices["meta"]) == dict

    all_symbols = [meta["symbol"] for meta in latest_prices["meta"].values()]
    assert all([feed_id in latest_prices["meta"] for feed_id in query_feed_ids])
    assert all([symbol in all_symbols for symbol in TEST_SYMBOLS])


def test_pyth_get_price_from_symbols(snx):
    # look up feed ids
    query_feed_ids = [
        snx.pyth.price_feed_ids[symbol]
        for symbol in TEST_SYMBOLS
        if symbol in snx.pyth.price_feed_ids
    ]
    assert len(query_feed_ids) == len(TEST_SYMBOLS)

    latest_prices = snx.pyth.get_price_from_symbols(TEST_SYMBOLS)
    assert latest_prices is not None
    assert latest_prices["price_update_data"] is not None
    assert type(latest_prices["meta"]) == dict

    all_symbols = [meta["symbol"] for meta in latest_prices["meta"].values()]
    assert all([feed_id in latest_prices["meta"] for feed_id in query_feed_ids])
    assert all([symbol in all_symbols for symbol in TEST_SYMBOLS])


def test_pyth_get_price_from_symbols_with_timestamp(snx):
    # get timestamp
    publish_time = int(time.time()) - TEST_LOOKBACK_SECONDS

    # look up feed ids
    query_feed_ids = [
        snx.pyth.price_feed_ids[symbol]
        for symbol in TEST_SYMBOLS
        if symbol in snx.pyth.price_feed_ids
    ]
    assert len(query_feed_ids) == len(TEST_SYMBOLS)

    latest_prices = snx.pyth.get_price_from_symbols(
        TEST_SYMBOLS, publish_time=publish_time
    )
    assert latest_prices is not None
    assert latest_prices["price_update_data"] is not None
    assert type(latest_prices["meta"]) == dict

    all_symbols = [meta["symbol"] for meta in latest_prices["meta"].values()]
    assert all([feed_id in latest_prices["meta"] for feed_id in query_feed_ids])
    assert all([symbol in all_symbols for symbol in TEST_SYMBOLS])


def test_pyth_cache_exists(snx):
    # fetch some prices
    snx.pyth.get_price_from_symbols(TEST_SYMBOLS)
    feed_ids = [snx.pyth.price_feed_ids[symbol] for symbol in TEST_SYMBOLS]
    key = ",".join(sorted(feed_ids))

    # check that they are all in the cache
    assert key in snx.pyth._cache
    assert snx.pyth._cache[key] is not None
    assert snx.pyth._cache[key]["price_update_data"] is not None
    assert snx.pyth._cache[key]["timestamp"] > 0


def test_pyth_cache_usage(snx):
    # fetch some prices
    pyth_data_og = snx.pyth.get_price_from_symbols(TEST_SYMBOLS)

    # fetch them again
    pyth_data_cache = snx.pyth.get_price_from_symbols(TEST_SYMBOLS)

    # check that the timestamps are the exact same
    assert pyth_data_og["timestamp"] == pyth_data_cache["timestamp"]


def test_pyth_no_cache(snx):
    # set ttl to zero
    snx.pyth.cache_ttl = 0

    # fetch some prices
    pyth_data_og = snx.pyth.get_price_from_symbols(TEST_SYMBOLS)

    # wait
    time.sleep(2)

    # fetch them again
    pyth_data_cache = snx.pyth.get_price_from_symbols(TEST_SYMBOLS)

    # check that the timestamps are different
    assert pyth_data_og["timestamp"] < pyth_data_cache["timestamp"]
