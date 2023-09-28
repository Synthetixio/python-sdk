import asyncio
import time
import logging
import warnings
import web3
from web3 import Web3
from web3.constants import ADDRESS_ZERO
from web3.types import TxParams
from .constants import DEFAULT_NETWORK_ID, DEFAULT_TRACKING_CODE, DEFAULT_SLIPPAGE, DEFAULT_GQL_ENDPOINT_PERPS, DEFAULT_GQL_ENDPOINT_RATES, DEFAULT_PRICE_SERVICE_ENDPOINTS, DEFAULT_REFERRER, DEFAULT_TRACKING_CODE
from .utils import wei_to_ether, ether_to_wei
from .contracts import load_contracts
from .pyth import Pyth
from .core import Core
from .perps import Perps
from .spot import Spot
# from .alerts import Alerts
from .queries import Queries

warnings.filterwarnings('ignore')


class Synthetix:
    def __init__(
            self,
            provider_rpc: str,
            address: str = ADDRESS_ZERO,
            private_key: str = None,
            network_id: int = None,
            core_account_id: int = None,
            perps_account_id: int = None,
            tracking_code: str = None,
            referrer: str = None,
            max_price_impact: float = DEFAULT_SLIPPAGE,
            use_estimate_gas: bool = True,
            gql_endpoint_perps: str = None,
            gql_endpoint_rates: str = None,
            satsuma_api_key: str = None,
            price_service_endpoint: str = None,
            telegram_token: str = None,
            telegram_channel_name: str = None):
        # set up logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)

        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)

        # set default values
        if network_id is None:
            network_id = DEFAULT_NETWORK_ID
        else:
            network_id = int(network_id)

        if tracking_code:
            self.tracking_code = tracking_code
        else:
            self.tracking_code = DEFAULT_TRACKING_CODE

        if referrer:
            self.referrer = referrer
        else:
            self.referrer = DEFAULT_REFERRER

        if max_price_impact:
            self.max_price_impact = max_price_impact
        else:
            self.max_price_impact = DEFAULT_SLIPPAGE

        # init account variables
        self.private_key = private_key
        self.address = address
        self.use_estimate_gas = use_estimate_gas
        self.provider_rpc = provider_rpc

        # init provider
        if provider_rpc.startswith('http'):
            self.provider_class = Web3.HTTPProvider
        elif provider_rpc.startswith('wss'):
            self.provider_class = Web3.WebsocketProvider
        else:
            raise Exception("RPC endpoint is invalid")
        
        # set up the web3 instance
        web3 = Web3(self.provider_class(self.provider_rpc))

        # check if the chain_id matches
        if web3.eth.chain_id != network_id:
            raise Exception(
                "The RPC `chain_id` must match the stored `network_id`")
        else:
            self.nonce = web3.eth.get_transaction_count(self.address)

        self.web3 = web3
        self.network_id = network_id

        # init contracts
        self.contracts = load_contracts(network_id)
        self.v2_markets, self.susd_legacy_token, self.susd_token, self.multicall = self._load_contracts()

        # init alerts
        # if telegram_token and telegram_channel_name:
        #     self.alerts = Alerts(telegram_token, telegram_channel_name)

        # init queries
        if not gql_endpoint_perps and self.network_id in DEFAULT_GQL_ENDPOINT_PERPS:
            gql_endpoint_perps = DEFAULT_GQL_ENDPOINT_PERPS[self.network_id]

        if not gql_endpoint_rates and self.network_id in DEFAULT_GQL_ENDPOINT_RATES:
            gql_endpoint_rates = DEFAULT_GQL_ENDPOINT_RATES[self.network_id]

        self.queries = Queries(
            synthetix=self,
            gql_endpoint_perps=gql_endpoint_perps,
            gql_endpoint_rates=gql_endpoint_rates,
            api_key=satsuma_api_key)

        # init pyth
        if not price_service_endpoint and self.network_id in DEFAULT_PRICE_SERVICE_ENDPOINTS:
            price_service_endpoint = DEFAULT_PRICE_SERVICE_ENDPOINTS[self.network_id]

        self.pyth = Pyth(self, price_service_endpoint=price_service_endpoint)
        self.core = Core(self, self.pyth, core_account_id)
        self.perps = Perps(self, self.pyth, perps_account_id)
        self.spot = Spot(self, self.pyth)

    def _load_contracts(self):
        """
        Initializes all necessary contracts
        ...

        Attributes
        ----------
        N/A
        """
        w3 = self.web3

        if 'PerpsV2MarketData' in self.contracts:
            data_definition = self.contracts['PerpsV2MarketData']
            data_address = w3.to_checksum_address(data_definition['address'])
            data_abi = data_definition['abi']

            marketdata_contract = w3.eth.contract(data_address, abi=data_abi)

            try:
                allmarketsdata = (
                    marketdata_contract.functions.allProxiedMarketSummaries().call())
            except Exception as e:
                allmarketsdata = []

            markets = {
                market[2].decode('utf-8').strip("\x00")[1:-4]: {
                    "market_address": market[0],
                    "asset": market[1].decode('utf-8').strip("\x00"),
                    "key": market[2],
                    "maxLeverage": w3.from_wei(market[3], 'ether'),
                    "price": market[4],
                    "marketSize": market[5],
                    "marketSkew": market[6],
                    "marketDebt": market[7],
                    "currentFundingRate": market[8],
                    "currentFundingVelocity": market[9],
                    "takerFee": market[10][0],
                    "makerFee": market[10][1],
                    "takerFeeDelayedOrder": market[10][2],
                    "makerFeeDelayedOrder": market[10][3],
                    "takerFeeOffchainDelayedOrder": market[10][4],
                    "makerFeeOffchainDelayedOrder": market[10][5],
                }
                for market in allmarketsdata
            }
        else:
            markets = {}

        # load sUSD legacy contract
        if 'sUSD' in self.contracts:
                susd_legacy_definition = self.contracts['sUSD']
                susd_legacy_address = w3.to_checksum_address(
                    susd_legacy_definition['address'])

                susd_legacy_token = w3.eth.contract(
                    susd_legacy_address, abi=susd_legacy_definition['abi'])
        else:
            susd_legacy_token = None

        # load sUSD contract
        if 'USDProxy' in self.contracts:
            susd_definition = self.contracts['USDProxy']
            susd_address = w3.to_checksum_address(susd_definition['address'])

            susd_token = w3.eth.contract(susd_address, abi=susd_definition['abi'])
        else:
            susd_token = None

        # load multicall contract
        if 'TrustedMulticallForwarder' in self.contracts:
            mc_definition = self.contracts['TrustedMulticallForwarder']
            mc_address = w3.to_checksum_address(mc_definition['address'])

            multicall = w3.eth.contract(mc_address, abi=mc_definition['abi'])
        else:
            multicall = None

        return markets, susd_legacy_token, susd_token, multicall

    def _get_tx_params(
        self, value=0, to=None
    ) -> TxParams:
        """
        Get the default tx params
        ...

        Attributes
        ----------
        value : int
            value to send in wei
        to : str
            address to send to

        Returns
        -------
        params : dict
            transaction parameters to be completed with another function
        """
        params: TxParams = {
            'from': self.address,
            'chainId': self.network_id,
            'value': value,
            'nonce': self.nonce
        }
        if to is not None:
            params['to'] = to
        return params

    def execute_transaction(self, tx_data: dict):
        """
        Execute a transaction given the TX data
        ...

        Attributes
        ----------
        tx_data : dict
            tx data to send transaction
        private_key : str
            private key of wallet sending transaction
        """
        if self.private_key is None:
            raise Exception("No private key specified.")

        if "gas" not in tx_data:
            if self.use_estimate_gas:
                tx_data["gas"] = int(self.web3.eth.estimate_gas(tx_data) * 1.2)
            else:
                tx_data["gas"] = 1500000

        signed_txn = self.web3.eth.account.sign_transaction(
            tx_data, private_key=self.private_key)
        tx_token = self.web3.eth.send_raw_transaction(
            signed_txn.rawTransaction)

        # increase nonce
        self.nonce += 1

        return self.web3.to_hex(tx_token)

    def get_susd_balance(self, address: str = None, legacy: bool = False) -> dict:
        """
        Gets current sUSD Balance in wallet
        ...

        Attributes
        ----------
        address : str
            address of wallet to check
        legacy : bool
            if true, check legacy sUSD contract
        Returns
        ----------
        Dict: wei and usd sUSD balance
        """
        if not address:
            address = self.address

        token = self.susd_legacy_token if legacy else self.susd_token

        balance = token.functions.balanceOf(
            self.address).call()
        return {"balance": wei_to_ether(balance)}

    def get_eth_balance(self, address: str = None) -> dict:
        """
        Gets current ETH Balance in wallet
        ...

        Attributes
        ----------
        address : str
            address of wallet to check
        Returns
        ----------
        Dict: wei and usd ETH balance
        """
        if not address:
            address = self.address

        weth_contract = self.web3.eth.contract(
            address=self.contracts['WETH']['address'], abi=self.contracts['WETH']['abi'])

        eth_balance = self.web3.eth.get_balance(address)
        weth_balance = weth_contract.functions.balanceOf(
            address).call()
        
        return {"eth": wei_to_ether(eth_balance), "weth": wei_to_ether(weth_balance)}

    # transactions
    def approve(
        self,
        token_address: str,
        target_address: str,
        amount: int = None,
        submit: bool = False
    ):
        """Approve an address to spend an ERC20 token"""
        # fix the amount
        amount = 2**256 - 1 if amount is None else ether_to_wei(amount)
        token_contract = self.web3.eth.contract(
            address=token_address, abi=self.contracts['USDProxy']['abi'])

        tx_params = self._get_tx_params()
        tx_params = token_contract.functions.approve(
            target_address, amount).build_transaction(tx_params)

        if submit:
            tx_hash = self.execute_transaction(tx_params)
            self.logger.info(
                f"Approving {target_address} to spend {amount / 1e18} {token_address} for {self.address}")
            self.logger.info(f"approve tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def wrap_eth(self, amount: float, submit: bool = False) -> str:
        """
        Wraps ETH into WETH
        ...

        Attributes
        ----------
        amount : float
            amount of ETH to wrap
        Returns
        ----------
        str: transaction hash
        """
        value_wei = ether_to_wei(max(amount, 0))
        weth_contract = self.web3.eth.contract(
            address=self.contracts['WETH']['address'], abi=self.contracts['WETH']['abi'])

        if amount < 0:
            fn_name = 'withdraw'
            tx_args = [ether_to_wei(abs(amount))]
        else:
            fn_name = 'deposit'
            tx_args = []

        tx_params = self._get_tx_params(
            value=value_wei
        )
        tx_params = weth_contract.functions[fn_name](*tx_args).build_transaction(tx_params)

        if submit:
            tx_hash = self.execute_transaction(tx_params)
            self.logger.info(f"Wrapping {amount} ETH for {self.address}")
            self.logger.info(f"wrap_eth tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params
