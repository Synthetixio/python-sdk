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
            price_service_endpoint='https://api.pyth.network'
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
        Fetch the pyth data for a list of tokens. The tokens must be in the constant
        file stored at the time the package is built. For a more reliable approach,
        specify the ``feed_id`` using the ``get_feeds_data`` method.
        
        Usage::

            >>> snx.pyth.get_tokens_data(['ETH', 'SNX'])
            [b'...', b'...']
    
        :param [str] tokens: List of tokens to fetch data for
        :return: List of price update data
        :rtype: [bytes] | None
        """
        self.snx.logger.info(f'Fetching data for tokens: {tokens}')
        feed_ids = [self.price_feed_ids[token] for token in tokens]

        price_update_data = self.get_feeds_data(feed_ids)
        return price_update_data

    def get_feeds_data(self, feed_ids: list):
        """
        Fetch the pyth data for a list of feed ids. This is the most reliable way to
        specify the exact feed you want to fetch data for. The feed ids can be found
        in the Pyth price service documentation, or at a price service API.
        
        Usage::
            
            >>> snx.pyth.get_feeds_data(['0x12345...', '0xabcde...'])
            [b'...', b'...']

        :param [str] feed_ids: List of feed ids to fetch data for
        :return: List of price update data
        :rtype: [bytes] | None
        """
        self.snx.logger.info(f'Fetching data for feed ids: {feed_ids}')
        url = f"{self._price_service_endpoint}/api/latest_vaas"
        params = {
            'ids[]': feed_ids
        }

        try:
            response = requests.get(url, params, timeout=10)
            price_update_data = [base64.b64decode(raw_pud) for raw_pud in response.json()]
            return price_update_data
        except Exception as err:
            print(err)
            return None
