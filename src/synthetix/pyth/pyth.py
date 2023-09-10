"""Module initializing a connection to the Pyth price service."""
import base64
import requests
from .constants import PRICE_FEED_IDS


class Pyth:
    """Class for interacting with the Pyth price service."""
    def __init__(self, network_id: int, price_service_endpoint: str = None):
        self._price_service_endpoint = price_service_endpoint
        if network_id in PRICE_FEED_IDS:
            self.price_feed_ids = PRICE_FEED_IDS[network_id]

    def price_update_data(self, feed_id=None, token_symbol=None):
        """
        Request price update data from the pyth price service
        ...

        Attributes
        ----------
        token_symbol : str
            token symbol from list of supported asset

        Returns
        ----------
        str: price update data
        """
        if feed_id is None and token_symbol is None:
            raise ValueError("Must provide either feed_id or token_symbol")

        if feed_id is None:
            feed_id = self.price_feed_ids[token_symbol]

        url = f"{self._price_service_endpoint}/api/latest_vaas"
        params = {
            'ids[]': [feed_id]
        }

        try:
            response = requests.get(url, params, timeout=10)
            return response.json(), base64.b64decode(response.json()[0])
        except Exception as err:
            print(err)
            return None
