"""Module initializing a connection to the Pyth price service."""

import json
from eth_utils import decode_hex
import base64
import requests
from .constants import PRICE_FEED_IDS


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

        price_update_token = snx.pyth.get_tokens_data(['SNX', 'ETH'])
        price_update_feed = snx.pyth.get_feeds_data(['0x12345...', '0xabcde...'])

    :param Synthetix snx: Synthetix class instance
    :param str price_service_endpoint: Pyth price service endpoint
    :return: Pyth class instance
    :rtype: Pyth
    """

    def __init__(self, snx, price_service_endpoint: str = None):
        self.snx = snx
        self.logger = snx.logger

        self._price_service_endpoint = price_service_endpoint
        self.price_feed_ids = {}

    # refactor this class using the following methods
    # def get_price_from_ids(self, feed_ids: [str])
    # def get_price_from_symbols(self, symbols: [str])
    # def get_benchmark_from_ids(self, feed_ids: [str], publish_time: int)
    # def get_benchmark_from_symbols(self, symbol: str, publish_time: int)

    def update_price_feed_ids(self, feed_ids: dict):
        """
        Update the price feed IDs for the Pyth price service.
        Additionally sets a lookup for feed_id to symbol.

        :param dict feed_ids: Dictionary of feed IDs to update
        """
        self.price_feed_ids.update(feed_ids)

        # reverse it and set a lookup from feed_id to symbol
        self.symbol_lookup = {v: k for k, v in self.price_feed_ids.items()}
        self.logger.info(f"Symbols: {self.symbol_lookup.keys()}")

    def _fetch_prices(self, feed_ids: [str], publish_time: int | None = None):
        """
        Fetch the latest Pyth price data for a list of feed ids. This is the most reliable way to
        specify the exact feed you want to fetch data for. The feed ids can be found
        in the Pyth price service documentation, or at a price service API. This function
        calls the V2 endpoint ``updates/price/latest`` to fetch the data.

        Usage::

            >>> snx.pyth.fetch_latest_price(['0x12345...', '0xabcde...'])
            [b'...', b'...']

        :param [str] feed_ids: List of feed ids to fetch data for
        :return: List of price update data
        :rtype: [bytes] | None
        """
        self.logger.info(f"Fetching data for feed ids: {feed_ids}")

        # query endpoint /v2/updates/price/latest
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
                    "symbol": self.symbol_lookup[f"0x{feed_data['id']}"],
                    "price": int(feed_data["price"]["price"])
                    * 10 ** feed_data["price"]["expo"],
                    "publish_time": feed_data["price"]["publish_time"],
                }
                for feed_data in response_data["parsed"]
            }

            return {"price_update_data": price_update_data, "meta": meta}
        except Exception as err:
            self.logger.error(f"Error fetching latest price data: {err}")
            return None

    def get_price_from_ids(self, feed_ids: [str], publish_time: int | None = None):
        """
        Fetch the latest Pyth price data for a list of feed ids. This is the most reliable way to
        specify the exact feed you want to fetch data for. The feed ids can be found
        in the Pyth price service documentation, or at a price service API. This function
        calls the V2 endpoint ``updates/price/latest`` to fetch the data.

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
        :return: Dictionary with price update data and metadata
        :rtype: dict | None
        """
        self.logger.info(f"Fetching data for feed ids: {feed_ids}")

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
        :return: Dictionary with price update data and metadata
        :rtype: dict | None
        """
        self.logger.info(f"Fetching data for symbols: {symbols}")
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

        pyth_data = self._fetch_prices(feed_ids, publish_time=publish_time)
        return pyth_data

    def get_tokens_data(self, tokens: [str]):
        """
        Fetch the latest Pyth price data for a list of tokens. The tokens must be in the constant
        file stored at the time the package is built. For a more reliable approach,
        specify the ``feed_id`` using the ``get_feeds_data`` method.  This function
        calls the endpoint ``latest_vaas`` to fetch the data.

        Usage::

            >>> snx.pyth.get_tokens_data(['ETH', 'SNX'])
            [b'...', b'...']

        :param [str] tokens: List of tokens to fetch data for
        :return: List of price update data
        :rtype: [bytes] | None
        """
        self.logger.info(f"Fetching data for tokens: {tokens}")
        feed_ids = [self.price_feed_ids[token] for token in tokens]

        price_update_data = self.get_feeds_data(feed_ids)
        return price_update_data

    def get_feeds_data(self, feed_ids: list):
        """
        Fetch the latest Pyth price data for a list of feed ids. This is the most reliable way to
        specify the exact feed you want to fetch data for. The feed ids can be found
        in the Pyth price service documentation, or at a price service API. This function
        calls the endpoint ``latest_vaas`` to fetch the data.

        Usage::

            >>> snx.pyth.get_feeds_data(['0x12345...', '0xabcde...'])
            [b'...', b'...']

        :param [str] feed_ids: List of feed ids to fetch data for
        :return: List of price update data
        :rtype: [bytes] | None
        """
        self.logger.info(f"Fetching data for feed ids: {feed_ids}")
        url = f"{self._price_service_endpoint}/api/latest_vaas"
        params = {"ids[]": feed_ids}

        try:
            response = requests.get(url, params, timeout=10)
            price_update_data = [
                base64.b64decode(raw_pud) for raw_pud in response.json()
            ]
            return price_update_data
        except Exception as err:
            print(err)
            return None

    def get_benchmark_data(self, feed_id: str, publish_time: int):
        """
        Fetch benchmark Pyth data for feed id and timestamp. This is the most reliable way to
        specify the exact feed you want to fetch data for a timestamp in the past. The feed ids can be found
        in the Pyth price service documentation, or at a price service API. Feed ids are also
        provided in the revert for ``OracleDataRequired`` errors.

        Usage::

            >>> snx.pyth.get_benchmark_data('0x12345...', 1621203900)
            ([b'...'], '0x12345...', 1621203900)

        :param str feed_id: A Pyth feed id
        :return: Tuple of price update data, feed id, and publish time
        :rtype: (bytes, str, int) | None
        """
        self.logger.info(f"Fetching benchmark data for {feed_id} at {publish_time}")
        url = f"{self._price_service_endpoint}/api/get_vaa"
        params = {
            "id": feed_id,
            "publish_time": publish_time,
        }

        try:
            response = requests.get(url, params, timeout=10)
            self.logger.info(f"Response: {response.json()}")

            # parse the response
            response_data = response.json()

            price_update_data = base64.b64decode(response_data["vaa"])
            publish_time = response_data["publishTime"]

            return price_update_data, feed_id, publish_time
        except Exception as err:
            self.logger.error(f"Error fetching benchmark data: {err}")
            return None

    def get_price_data(self, feed_id: str):
        """
        Fetch latest Pyth data for a feed id. This method will help
        fetch price data along with metadata, like the publish timestamp. The feed id
        can be found in the Pyth price service documentation, or at a price service API.

        Usage::

            >>> snx.pyth.get_price_data('0x12345...')
            ([b'...'], '0x12345...', 1621203900)

        :param [str] feed_ids: A Pyth feed id
        :return: Tuple of price update data, feed id, and publish timestamp
        :rtype: (bytes, str, int) | None
        """
        self.logger.info(f"Fetching latest data for feed ids: {feed_id}")
        url = f"{self._price_service_endpoint}/api/latest_price_feeds"
        params = {"ids[]": [feed_id], "binary": "true"}

        try:
            response = requests.get(url, params, timeout=10)

            # parse the response
            feed_datas = response.json()

            price_update_data = base64.b64decode(feed_data["vaa"])
            feed_id = base64.b64decode(feed_data["id"])
            timestamp = feed_data["price"]["publish_time"]

            return price_update_data, feed_id, timestamp
        except Exception as err:
            print(err)
            return None
