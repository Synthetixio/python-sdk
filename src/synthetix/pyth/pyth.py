"""Module initializing a connection to the Pyth price service."""

import time
import requests
from eth_utils import decode_hex


class Pyth:
    """
    Class for interacting with the Pyth price service. The price service is
    connected to the endpoint specified as ``price_service_endpoint`` when
    initializing the ``Synthetix`` class::

        snx = Synthetix(
            ...,
            price_service_endpoint='https://hermes.pyth.network'
        )

    If an endpoint isn't specified, the default endpoint is used. The default
    endpoint should be considered unreliable for production applications.

    The ``Pyth`` class is used to fetch the latest price update data for a list
    of tokens or feed ids::

        price_data_symbol = snx.pyth.get_price_from_symbols(['SNX', 'ETH'])
        price_data_id = snx.pyth.get_price_from_ids(['0x12345...', '0xabcde...'])

    :param Synthetix snx: Synthetix class instance
    :param str price_service_endpoint: Pyth price service endpoint
    :param int cache_ttl: Cache time-to-live in seconds
    :return: Pyth class instance
    :rtype: Pyth
    """

    def __init__(self, snx, cache_ttl, price_service_endpoint: str = None):
        self.snx = snx
        self.logger = snx.logger

        self._price_service_endpoint = price_service_endpoint
        self.price_feed_ids = {}
        self.symbol_lookup = {}

        # set up a cache
        self.cache_ttl = cache_ttl
        self._cache = {}

    def _check_cache(self, feed_ids: [str]):
        """
        Check the cache for the latest price data for a list of feed ids. The cache
        is used to store the latest price data for a list of feed ids. The cache
        is invalidated after a certain time-to-live.

        :param [str] feed_ids: List of feed ids to fetch data for
        :return: Cached price data
        :rtype: dict | None
        """
        self._purge_cache()
        cache_key = ",".join(sorted(feed_ids))
        if cache_key in self._cache:
            cache_data = self._cache[cache_key]
            if int(time.time()) - cache_data["timestamp"] < self.cache_ttl:
                return cache_data
        return None

    def _purge_cache(self):
        """
        Purge the cache of all data that is past the time-to-live.
        """
        self._cache = {
            k: v
            for k, v in self._cache.items()
            if int(time.time()) - v["timestamp"] < self.cache_ttl
        }

    def update_price_feed_ids(self, feed_ids: dict):
        """
        Update the price feed IDs for the Pyth price service.
        Additionally sets a lookup for feed_id to symbol.

        :param dict feed_ids: Dictionary of feed IDs to update
        """
        self.price_feed_ids.update(feed_ids)

        # reverse it and set a lookup from feed_id to symbol
        self.symbol_lookup = {v: k for k, v in self.price_feed_ids.items()}

    def _fetch_prices(self, feed_ids: [str], publish_time: int | None = None):
        """
        An internal method for fetching price data from the Pyth price service. This
        method is used by the public methods ``get_price_from_ids`` and
        ``get_price_from_symbols``. The method fetches the latest price data for a list
        of feed ids, deciding which endpoint to use based on the presence of a publish time.

        :param [str] feed_ids: List of feed ids to fetch data for
        :param int publish_time: Publish time for benchmark data
        :return: List of price update data
        :rtype: [bytes] | None
        """
        market_names = ",".join(
            [
                self.symbol_lookup[feed_id]
                for feed_id in feed_ids
                if feed_id in self.symbol_lookup
            ]
        )
        self.logger.info(
            f"Fetching Pyth data for {len(feed_ids)} markets ({market_names}) @ {publish_time if publish_time else 'latest'}"
        )

        self.logger.debug(f"Fetching data for feed ids: {feed_ids}")

        params = {"ids[]": feed_ids, "encoding": "hex"}
        if publish_time is None:
            # fetch latest data
            url = f"{self._price_service_endpoint}/v2/updates/price/latest"
        else:
            # fetch benchmark data
            url = f"{self._price_service_endpoint}/v2/updates/price/{publish_time}"

        try:
            response = requests.get(url, params, timeout=10)
            if response.status_code != 200:
                if response.text and "Price ids not found" in response.text:
                    self.logger.info(f"Removing missing price feeds: {response.text}")
                    feed_ids = [
                        feed_id for feed_id in feed_ids if feed_id not in response.text
                    ]
                    return self._fetch_prices(feed_ids, publish_time=publish_time)

                self.logger.error(f"Error fetching latest price data: {response.text}")
                return None

            response_data = response.json()

            # decode the price data
            price_update_data = [
                decode_hex(f"0x{raw_pud}")
                for raw_pud in response_data["binary"]["data"]
            ]

            # enrich some metadata
            meta = {
                f"0x{feed_data['id']}": {
                    "symbol": (
                        self.symbol_lookup[f"0x{feed_data['id']}"]
                        if f"0x{feed_data['id']}" in self.symbol_lookup
                        else "N/A"
                    ),
                    "price": int(feed_data["price"]["price"])
                    * 10 ** feed_data["price"]["expo"],
                    "publish_time": feed_data["price"]["publish_time"],
                }
                for feed_data in response_data["parsed"]
            }

            pyth_data = {
                "timestamp": int(time.time()),
                "price_update_data": price_update_data,
                "meta": meta,
            }

            # update the cache
            # only update if ttl > 0
            if self.cache_ttl > 0:
                self._cache[",".join(sorted(feed_ids))] = pyth_data
            return pyth_data
        except Exception as err:
            self.logger.error(f"Error fetching latest price data: {err}")
            return None

    def get_price_from_ids(self, feed_ids: [str], publish_time: int | None = None):
        """
        Fetch the latest Pyth price data for a list of feed ids. This is the most reliable way to
        specify the exact feed you want to fetch data for. The feed ids can be found
        in the Pyth price service documentation, or at a price service API. This function
        calls the V2 endpoint ``updates/price/latest`` to fetch the data. Specify a publish time
        in order to fetch benchmark data.

        Usage::

            >>> snx.pyth.get_price_from_ids(['0x12345...', '0xabcde...'])
            {
                "price_update_data": [b'...', b'...'],
                "meta": {
                    "0x12345...": {
                        "symbol": "ETH",
                        "price": 2000,
                        "publish_time": 1621203900
                }
            }

        :param [str] feed_ids: List of feed ids to fetch data for
        :param int publish_time: Publish time for benchmark data
        :return: Dictionary with price update data and metadata
        :rtype: dict | None
        """
        # check the cache
        cached_data = (
            self._check_cache(feed_ids)
            if self.cache_ttl > 0 and publish_time is None
            else None
        )
        if cached_data:
            self.logger.info("Using cached Pyth data")
            return cached_data
        else:
            pyth_data = self._fetch_prices(feed_ids, publish_time=publish_time)
            return pyth_data

    def get_price_from_symbols(self, symbols: [str], publish_time: int | None = None):
        """
        Fetch the latest Pyth price data for a list of market symbols. This
        function is the same as ``get_price_from_ids`` but uses the symbol
        to fetch the feed id from the lookup table.

        Usage::

            >>> snx.pyth.get_price_from_symbols(['ETH', 'BTC'])
            {
                "price_update_data": [b'...', b'...'],
                "meta": {
                    "0x12345...": {
                        "symbol": "ETH",
                        "price": 2000,
                        "publish_time": 1621203900
                }
            }

        :param [str] symbols: List of symbols to fetch data for
        :param int publish_time: Publish time for benchmark data
        :return: Dictionary with price update data and metadata
        :rtype: dict | None
        """
        self.logger.debug(f"Fetching data for symbols: {symbols}")
        # look up all symbols that exist
        feed_ids = [
            self.price_feed_ids[symbol]
            for symbol in symbols
            if symbol in self.price_feed_ids
        ]
        if len(feed_ids) != len(symbols):
            missing_symbols = set(symbols) - set(self.price_feed_ids.keys())
            self.logger.error(f"Feed ids not found for symbols: {missing_symbols}")
            return None

        # check the cache
        cached_data = (
            self._check_cache(feed_ids)
            if self.cache_ttl > 0 and publish_time is None
            else None
        )
        if cached_data:
            self.logger.info("Using cached Pyth data")
            return cached_data
        else:
            pyth_data = self._fetch_prices(feed_ids, publish_time=publish_time)
            return pyth_data
