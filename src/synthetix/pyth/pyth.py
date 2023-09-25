"""Module initializing a connection to the Pyth price service."""
import base64
import requests
from .constants import PRICE_FEED_IDS


class Pyth:
    """Class for interacting with the Pyth price service."""
    def __init__(self, snx, price_service_endpoint: str = None):
        self.snx = snx
        
        self._price_service_endpoint = price_service_endpoint
        if snx.network_id in PRICE_FEED_IDS:
            self.price_feed_ids = PRICE_FEED_IDS[snx.network_id]

    def get_tokens_data(self, tokens: list):
        """Fetch the pyth data for a list of tokens"""
        self.snx.logger.info(f'Fetching data for tokens: {tokens}')
        feed_ids = [self.price_feed_ids[token] for token in tokens]

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

    def get_feeds_data(self, feed_ids: list):
        """Fetch the pyth data for a list of feed ids"""
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
