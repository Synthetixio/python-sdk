import os
import time
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# ETH price feed id, and a timestamp from 5 minutes ago
TEST_FEED_ID = "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace"
TEST_PUBLISH_TIME = int(time.time()) - 300


# tests
def test_pyth(snx, logger):
    """The instance has a Pyth class instance"""
    assert snx.pyth is not None


def test_benchmark(snx, logger):
    """Can fetch benchmark data"""
    price_update_data, feed_id, publish_time = snx.pyth.get_benchmark_data(
        TEST_FEED_ID, TEST_PUBLISH_TIME
    )

    assert price_update_data is not None
    assert feed_id == TEST_FEED_ID
    assert publish_time == TEST_PUBLISH_TIME


def test_benchmark_v2(snx, logger):
    """Can fetch benchmark data from a V2 endpoint"""
    price_update_data, feed_id, publish_time = snx.pyth.get_benchmark_data_v2(
        TEST_FEED_ID, TEST_PUBLISH_TIME
    )

    assert price_update_data is not None
    assert feed_id == TEST_FEED_ID
    assert publish_time == TEST_PUBLISH_TIME
