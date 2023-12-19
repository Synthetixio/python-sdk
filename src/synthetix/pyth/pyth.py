"""Module initializing a connection to the Pyth price service."""
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

        self._price_service_endpoint = price_service_endpoint
        if snx.network_id in PRICE_FEED_IDS:
            self.price_feed_ids = PRICE_FEED_IDS[snx.network_id]

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
        self.snx.logger.info(f"Fetching data for tokens: {tokens}")
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
        self.snx.logger.info(f"Fetching data for feed ids: {feed_ids}")
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
        self.snx.logger.info(f"Fetching benchmark data for {feed_id} at {publish_time}")
        url = f"{self._price_service_endpoint}/api/get_vaa"
        params = {
            "id": feed_id,
            "publish_time": publish_time,
        }

        try:
            response = requests.get(url, params, timeout=10)

            # parse the response
            response_data = response.json()

            price_update_data = base64.b64decode(response_data["vaa"])
            publish_time = response_data["publishTime"]

            return price_update_data, feed_id, publish_time
        except Exception as err:
            print(err)
            return None

    def get_latest_data(self, feed_id: str):
        """
        Fetch latest Pyth data for a feed id. This method will help
        fetch price data along with metadata, like the publish timestamp. The feed id
        can be found in the Pyth price service documentation, or at a price service API.

        Usage::

            >>> snx.pyth.get_latest_data('0x12345...')
            ([b'...'], '0x12345...', 1621203900)

        :param [str] feed_ids: A Pyth feed id
        :return: Tuple of price update data, feed id, and publish timestamp
        :rtype: (bytes, str, int) | None
        """
        self.snx.logger.info(f"Fetching latest data for feed ids: {feed_id}")
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
