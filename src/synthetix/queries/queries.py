import time
import requests
import logging
import pandas as pd
from decimal import Decimal
from web3.constants import ADDRESS_ZERO
from gql import Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.requests import RequestsHTTPTransport
from .gql import queries
from .config import config


def convert_wei(x):
    """Converts wei values using 18 decimal places"""
    try:
        return float(Decimal(x) / Decimal(10**18))
    except:
        return x


def convert_int(x):
    """Converts a string to an int if possible"""
    try:
        return Decimal(x)
    except:
        return x


def convert_from_bytes(x):
    """Converts bytes to readable strings"""
    return bytearray.fromhex(x[2:]).decode().replace("\x00", "")


def convert_to_bytes(input_string):
    """Converts readable strings to bytes"""
    hex_string = input_string.encode("utf-8").hex()
    hex_string = hex_string.ljust(64, "0")
    return "0x" + hex_string


def camel_to_snake(name):
    """Converts camelCase to snake_case"""
    snake = ""
    for char in name:
        if char.isupper():
            if snake != "":
                snake += "_"
            snake += char.lower()
        else:
            snake += char
    return snake


def clean_df(df, config):
    """Converts datatypes and column names to match the config"""
    new_columns = [camel_to_snake(col) for col in df.columns]
    for col in df.columns:
        type = config[col]
        if type == "Wei":
            df[col] = df[col].apply(convert_wei)
        elif type == "BigInt":
            df[col] = df[col].apply(convert_int)
        elif type == "Bytes":
            df[col] = df[col].apply(convert_from_bytes)
    df.columns = new_columns
    return df


class Queries:
    def __init__(
        self,
        synthetix,
        gql_endpoint_perps: str = None,
        gql_endpoint_rates: str = None,
        api_key: str = None,
    ):
        self.synthetix = synthetix
        self._gql_endpoint_rates = gql_endpoint_rates

        if gql_endpoint_perps is not None and "satsuma" in gql_endpoint_perps:
            self._gql_endpoint_perps = gql_endpoint_perps.format(api_key=api_key)
        else:
            self._gql_endpoint_perps = gql_endpoint_perps

        # set logging for gql
        logging.getLogger("gql").setLevel(logging.WARNING)

    def _get_headers(self):
        return {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
        }

    def _make_request(self, url: str, payload: dict):
        """Make a request to the subgraph and return the results"""
        try:
            response = requests.post(url, headers=self._get_headers(), json=payload)
            return response.json()["data"]
        except Exception as e:
            print(e)
            return None

    async def _run_query(self, query, params, accessor, url):
        """Run a GraphQL query on the subgraph and return the results as a dataframe"""
        transport = AIOHTTPTransport(url=url)

        async with Client(
            transport=transport,
            fetch_schema_from_transport=True,
        ) as session:
            done_fetching = False
            all_results = []
            while not done_fetching:
                result = await session.execute(query, variable_values=params)
                if len(result[accessor]) > 0:
                    all_results.extend(result[accessor])
                    params["last_id"] = all_results[-1]["id"]
                else:
                    done_fetching = True

            df = pd.DataFrame(all_results)
            return df

    def _run_query_sync(self, query, params, accessor, url):
        """Run a GraphQL query on the subgraph and return the results as a dataframe"""
        transport = RequestsHTTPTransport(url=url)

        with Client(
            transport=transport,
            fetch_schema_from_transport=True,
        ) as session:
            done_fetching = False
            all_results = []
            while not done_fetching:
                result = session.execute(query, variable_values=params)
                if len(result[accessor]) > 0:
                    all_results.extend(result[accessor])
                    params["last_id"] = all_results[-1]["id"]
                else:
                    done_fetching = True

            df = pd.DataFrame(all_results)
            return df

    async def candles(self, asset, hours_back=72, period=1800):
        """
        Gets historical data from subgraph
        ...

        Attributes
        ----------
        asset : str
            token symbol from list of supported asset
        hours_back : int
            Number of hours to go back in time
        period : int
            Timescale of candles in seconds (ex 3600 = 1 hour)

        Returns
        ----------
        str: token transfer Tx id
        """
        current_timestamp = int(time.time())
        # Subtract hours from current timestamp
        day_ago = current_timestamp - (hours_back * 60 * 60)

        # configure the query
        url = self._gql_endpoint_rates
        params = {
            "last_id": "",
            "asset": asset,
            "min_timestamp": day_ago,
            "max_timestamp": current_timestamp,
            "period": period,
        }
        result = await self._run_query(queries["candles"], params, "candles", url)
        return clean_df(result, config["candles"])

    async def trades_for_market(
        self,
        asset: str = None,
        min_timestamp: int = 0,
        max_timestamp: int = int(time.time()),
    ):
        """
        Gets historical trades for a specified asset, or all assets if none specified
        ...

        Attributes
        ----------
        asset : str
            Asset to fetch. If none specified, fetches all assets

        Returns
        ----------
        df: pandas DataFrame containing trades for the market
        """
        if not asset:
            market_keys = [
                self.synthetix.v2_markets[asset]["key"].hex()
                for asset in self.synthetix.v2_markets.keys()
            ]
        else:
            market_keys = [self.synthetix.v2_markets[asset]["key"].hex()]

        # configure the query
        url = self._gql_endpoint_perps
        params = {
            "last_id": "",
            "market_keys": market_keys,
            "min_timestamp": min_timestamp,
            "max_timestamp": max_timestamp,
        }
        result = await self._run_query(
            queries["trades_market"], params, "futuresTrades", url
        )
        return clean_df(result, config["trades"])

    async def trades_for_account(
        self,
        account: str = ADDRESS_ZERO,
        min_timestamp: int = 0,
        max_timestamp: int = int(time.time()),
    ):
        """
        Gets historical trades for a specified account
        ...

        Attributes
        ----------
        account : str
            Address of the account to filter

        Returns
        ----------
        df: pandas DataFrame containing trades for the account
        """
        if self.synthetix.address is not None and account == ADDRESS_ZERO:
            account = self.synthetix.address
        elif account == ADDRESS_ZERO:
            raise Exception("No account specified")

        # configure the query
        url = self._gql_endpoint_perps
        params = {
            "last_id": "",
            "account": account,
            "min_timestamp": min_timestamp,
            "max_timestamp": max_timestamp,
        }
        result = await self._run_query(
            queries["trades_account"], params, "futuresTrades", url
        )
        return clean_df(result, config["trades"])

    async def positions_for_market(self, asset: str = None, open_only: bool = False):
        """
        Gets historical positions for a specified asset, or all assets if none specified
        ...

        Attributes
        ----------
        asset : str
            Asset to fetch. If none specified, fetches all assets
        open_only : bool
            If true, only fetches open positions

        Returns
        ----------
        df: pandas DataFrame containing positions for the market
        """
        if not asset:
            market_keys = [
                self.synthetix.v2_markets[asset]["key"].hex()
                for asset in self.synthetix.v2_markets.keys()
            ]
        else:
            market_keys = [self.synthetix.v2_markets[asset]["key"].hex()]

        # configure the query
        url = self._gql_endpoint_perps
        params = {
            "last_id": "",
            "market_keys": market_keys,
            "is_open": [True] if open_only else [True, False],
        }
        result = await self._run_query(
            queries["positions_market"], params, "futuresPositions", url
        )
        return clean_df(result, config["positions"])

    async def positions_for_account(self, account: str = ADDRESS_ZERO, open_only=False):
        """
        Gets historical positions for a specified account, or the connected wallet
        ...

        Attributes
        ----------
        asset : str
            Asset to fetch. If none specified, fetches all assets
        open_only : bool
            If true, only fetches open positions

        Returns
        ----------
        df: pandas DataFrame containing positions for the account
        """
        if self.synthetix.address is not None and account == ADDRESS_ZERO:
            account = self.synthetix.address
        elif account == ADDRESS_ZERO:
            raise Exception("No account specified")

        # configure the query
        url = self._gql_endpoint_perps
        params = {
            "last_id": "",
            "account": account,
            "is_open": [True] if open_only else [True, False],
        }
        result = await self._run_query(
            queries["positions_account"], params, "futuresPositions", url
        )
        return clean_df(result, config["positions"])

    async def transfers_for_market(
        self,
        asset: str = None,
        min_timestamp: int = 0,
        max_timestamp: int = int(time.time()),
    ):
        """
        Gets historical transfers for a specified asset, or all assets if none specified
        ...

        Attributes
        ----------
        asset : str
            Asset to fetch. If none specified, fetches all assets
        min_timestamp : int
            Minimum timestamp to fetch transfers for
        max_timestamp : int
            Maximum timestamp to fetch transfers for

        Returns
        ----------
        df: pandas DataFrame containing transfers for the specified params
        """
        if not asset:
            market_keys = [
                self.synthetix.v2_markets[asset]["key"].hex()
                for asset in self.synthetix.v2_markets.keys()
            ]
        else:
            market_keys = [self.synthetix.v2_markets[asset]["key"].hex()]

        # configure the query
        url = self._gql_endpoint_perps
        params = {
            "last_id": "",
            "market_keys": market_keys,
            "min_timestamp": min_timestamp,
            "max_timestamp": max_timestamp,
        }
        result = await self._run_query(
            queries["transfers_market"], params, "futuresMarginTransfers", url
        )
        return clean_df(result, config["transfers"])

    async def transfers_for_account(
        self,
        account: str = ADDRESS_ZERO,
        min_timestamp: int = 0,
        max_timestamp: int = int(time.time()),
    ):
        """
        Gets historical transfers for a specified account, or the connected wallet
        ...

        Attributes
        ----------
        account : str
            Address of the account to filter
        min_timestamp : int
            Minimum timestamp to fetch transfers for
        max_timestamp : int
            Maximum timestamp to fetch transfers for

        Returns
        ----------
        df: pandas DataFrame containing transfers for the specified params
        """
        if self.synthetix.address is not None and account == ADDRESS_ZERO:
            account = self.synthetix.address
        elif account == ADDRESS_ZERO:
            raise Exception("No account specified")

        # configure the query
        url = self._gql_endpoint_perps
        params = {
            "last_id": "",
            "account": account,
            "min_timestamp": min_timestamp,
            "max_timestamp": max_timestamp,
        }
        result = await self._run_query(
            queries["transfers_account"], params, "futuresMarginTransfers", url
        )
        return clean_df(result, config["transfers"])

    async def funding_rates(
        self,
        asset: str = None,
        min_timestamp: int = 0,
        max_timestamp: int = int(time.time()),
    ):
        """
        Gets historical funding rates for a specified asset, or all assets if none specified
        ...

        Attributes
        ----------
        asset : str
            Asset to fetch. If none specified, fetches all assets
        min_timestamp : int
            Minimum timestamp to fetch transfers for
        max_timestamp : int
            Maximum timestamp to fetch transfers for

        Returns
        ----------
        df: pandas DataFrame containing funding rates for the specified params
        """
        if not asset:
            market_keys = [
                self.synthetix.v2_markets[asset]["key"].hex()
                for asset in self.synthetix.v2_markets.keys()
            ]
        else:
            market_keys = [self.synthetix.v2_markets[asset]["key"].hex()]

        # configure the query
        url = self._gql_endpoint_perps
        params = {
            "last_id": "",
            "market_keys": market_keys,
            "min_timestamp": min_timestamp,
            "max_timestamp": max_timestamp,
        }
        result = await self._run_query(
            queries["funding_rates"], params, "fundingRateUpdates", url
        )
        return clean_df(result, config["funding_rates"])
