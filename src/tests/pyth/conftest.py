import pytest


@pytest.fixture(scope="module")
def feed_ids(snx):
    # check the SDK for feed ids
    perps_markets = snx.perps.markets_by_name
    feed_ids = {market: perps_markets[market]["feed_id"] for market in perps_markets}

    # TODO: get backup feeds from the pyth API

    snx.logger.info(f"Feed ids available for: {feed_ids.keys()}")
    return feed_ids
