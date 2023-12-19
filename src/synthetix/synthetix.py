import asyncio
import time
import logging
import warnings
import web3
from web3 import Web3
from web3.constants import ADDRESS_ZERO
from web3.types import TxParams
from .constants import (
    DEFAULT_NETWORK_ID,
    DEFAULT_TRACKING_CODE,
    DEFAULT_SLIPPAGE,
    DEFAULT_GQL_ENDPOINT_PERPS,
    DEFAULT_GQL_ENDPOINT_RATES,
    DEFAULT_PRICE_SERVICE_ENDPOINTS,
    DEFAULT_REFERRER,
    DEFAULT_TRACKING_CODE,
)
from .utils import wei_to_ether, ether_to_wei
from .contracts import load_contracts
from .pyth import Pyth
from .core import Core
from .perps import Perps
from .spot import Spot

# from .alerts import Alerts
from .queries import Queries

warnings.filterwarnings("ignore")


class Synthetix:
    """
    The main class for interacting with the Synthetix protocol. The class
    requires a provider RPC endpoint and a wallet address::

            snx = Synthetix(
                provider_rpc='https://base-mainnet.infura.io/v3/...',
                network_id=8453,
                address='0x12345...'
            )

    The class can be initialized with a private key to allow for transactions
    to be signed and sent to your RPC::

                snx = Synthetix(
                    provider_rpc='https://base-mainnet.infura.io/v3/...',
                    network_id=8453,
                    address='0x12345...',
                    private_key='0xabcde...'
                )

    :param str provider_rpc: An RPC endpoint to use for the provider that interacts
        with the smart contracts. This must match the ``network_id``.
    :param str mainnet_rpc: A mainnet RPC endpoint to use for the provider that
        fetches deployments from the Cannon registry.
    :param str ipfs_gateway: An IPFS gateway to use for fetching deployments from Cannon.
    :param str address: Wallet address to use as a default. If a private key is
        specified, this address will be used to sign transactions.
    :param str private_key: Private key of the provided wallet address. If specified,
        the wallet will be enabled to sign and submit transactions.
    :param int network_id: Network ID for the chain to connect to. This must match
        the chain ID of the RPC endpoint.
    :param int core_account_id: A default ``account_id`` for core transactions.
        Setting a default will avoid the need to specify on each transaction. If
        not specified, the first ``account_id`` will be used.
    :param int perps_account_id: A default ``account_id`` for perps transactions.
        Setting a default will avoid the need to specify on each transaction. If
        not specified, the first ``account_id`` will be used.
    :param str tracking_code: Set a tracking code for trades.
    :param str referrer: Set a referrer address for trades.
    :param float max_price_impact: Max price impact setting for trades,
        specified as a percentage. This setting applies to both spot and
        perps markets.
    :param bool use_estimate_gas: Use estimate gas for transactions. If false,
        it is assumed you will add a gas limit to all transactions.
    :param str gql_endpoint_perps: GraphQL endpoint for perps data.
    :param str satsuma_api_key: API key for Satsuma. If the endpoint is from
        Satsuma, the API key will be automatically added to the request.
    :param str price_service_endpoint: Endpoint for a Pyth price service. If
        not specified, a default endpoint is used.
    :return: Synthetix class instance
    :rtype: Synthetix
    """

    def __init__(
        self,
        provider_rpc: str,
        mainnet_rpc: str = "https://eth.llamarpc.com",
        ipfs_gateway: str = "https://ipfs.io/ipfs",
        address: str = ADDRESS_ZERO,
        private_key: str = None,
        network_id: int = None,
        core_account_id: int = None,
        perps_account_id: int = None,
        tracking_code: str = None,
        referrer: str = None,
        max_price_impact: float = DEFAULT_SLIPPAGE,
        use_estimate_gas: bool = True,
        cannon_config: dict = None,
        gql_endpoint_perps: str = None,
        gql_endpoint_rates: str = None,
        satsuma_api_key: str = None,
        price_service_endpoint: str = None,
        telegram_token: str = None,
        telegram_channel_name: str = None,
    ):
        # set up logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)

        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
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
        self.cannon_config = cannon_config
        self.provider_rpc = provider_rpc
        self.mainnet_rpc = mainnet_rpc
        self.ipfs_gateway = ipfs_gateway

        # init chain provider
        if provider_rpc.startswith("http"):
            web3 = Web3(Web3.HTTPProvider(self.provider_rpc))
        elif provider_rpc.startswith("wss"):
            web3 = Web3(Web3.WebsocketProvider(self.provider_rpc))
        else:
            raise Exception("Provider RPC endpoint is invalid")

        # check if the chain_id matches
        if web3.eth.chain_id != network_id:
            raise Exception("The RPC `chain_id` must match the stored `network_id`")
        else:
            self.nonce = web3.eth.get_transaction_count(self.address)

        self.web3 = web3
        self.network_id = network_id

        # init contracts
        self.contracts = load_contracts(self)
        (
            self.v2_markets,
            self.susd_legacy_token,
            self.susd_token,
            self.multicall,
        ) = self._load_contracts()

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
            api_key=satsuma_api_key,
        )

        # init pyth
        if (
            not price_service_endpoint
            and self.network_id in DEFAULT_PRICE_SERVICE_ENDPOINTS
        ):
            price_service_endpoint = DEFAULT_PRICE_SERVICE_ENDPOINTS[self.network_id]

        self.pyth = Pyth(self, price_service_endpoint=price_service_endpoint)
        self.core = Core(self, core_account_id)
        self.perps = Perps(self, self.pyth, perps_account_id)
        self.spot = Spot(self, self.pyth)

    def _load_contracts(self):
        """
        Initializes and sets up contracts according to the connected chain.
        On calling this function, the following contracts are connected and set up:
        * ``PerpsV2MarketData``
        * ``PerpsV2MarketProxy`` (for each V2 market)
        * ``sUSD`` contracts for both V3 and legacy sUSD.
        * ``TrustedMulticallForwarder`` (if available)

        These are stored as methods on the base Synthetix object::

            >>> snx.susd_token.address
            0x...

        :return: web3 contracts
        :rtype: [contract, contract, contract, contract]
        """
        w3 = self.web3

        if "PerpsV2MarketData" in self.contracts:
            data_definition = self.contracts["PerpsV2MarketData"]
            data_address = w3.to_checksum_address(data_definition["address"])
            data_abi = data_definition["abi"]

            marketdata_contract = w3.eth.contract(data_address, abi=data_abi)

            try:
                allmarketsdata = (
                    marketdata_contract.functions.allProxiedMarketSummaries().call()
                )
            except Exception as e:
                allmarketsdata = []

            markets = {
                market[2]
                .decode("utf-8")
                .strip("\x00")[1:-4]: {
                    "market_address": market[0],
                    "asset": market[1].decode("utf-8").strip("\x00"),
                    "key": market[2],
                    "maxLeverage": w3.from_wei(market[3], "ether"),
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
        if "sUSD" in self.contracts:
            susd_legacy_definition = self.contracts["sUSD"]
            susd_legacy_address = w3.to_checksum_address(
                susd_legacy_definition["address"]
            )

            susd_legacy_token = w3.eth.contract(
                susd_legacy_address, abi=susd_legacy_definition["abi"]
            )
        else:
            susd_legacy_token = None

        # load sUSD contract
        if "USDProxy" in self.contracts:
            susd_definition = self.contracts["USDProxy"]
            susd_address = w3.to_checksum_address(susd_definition["address"])

            susd_token = w3.eth.contract(susd_address, abi=susd_definition["abi"])
        else:
            susd_token = None

        # load multicall contract
        if "TrustedMulticallForwarder" in self.contracts:
            mc_definition = self.contracts["TrustedMulticallForwarder"]
            mc_address = w3.to_checksum_address(mc_definition["address"])

            multicall = w3.eth.contract(mc_address, abi=mc_definition["abi"])
        else:
            multicall = None

        return markets, susd_legacy_token, susd_token, multicall

    def _get_tx_params(self, value=0, to=None) -> TxParams:
        """
        A helper function to prepare transaction parameters. This function
        will set up the transaction based on the parameters at initialization,
        but leave the ``data`` parameter empty.

        :param int value: value to send with transaction
        :param str | None to: address to send transaction to
        :return: A prepared transaction without the ``data`` parameter
        :rtype: TxParams
        """
        params: TxParams = {
            "from": self.address,
            "chainId": self.network_id,
            "value": value,
            "nonce": self.nonce,
        }
        if to is not None:
            params["to"] = to
        return params

    def wait(self, tx_hash: str, timeout: int = 120):
        """
        Wait for a transaction to be confirmed and return the receipt.
        The function will throw an error if the timeout is exceeded.
        Use this as a helper function to wait for a transaction to be confirmed,
        then check the results and react accordingly.

        :param str tx_hash: transaction hash to wait for
        :param int timeout: timeout in seconds
        :return: A transaction receipt
        :rtype: dict
        """
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        return receipt

    def execute_transaction(self, tx_data: dict):
        """
        Execute a provided transaction. This function will be signed with the provided
        private key and submitted to the connected RPC. The ``Synthetix`` object tracks
        the nonce internally, and will handle estimating gas limits if they are not
        provided.

        :param dict tx_data: transaction data
        :return: A transaction hash
        :rtype: str
        """
        if self.private_key is None:
            raise Exception("No private key specified.")

        if "gas" not in tx_data:
            if self.use_estimate_gas:
                tx_data["gas"] = int(self.web3.eth.estimate_gas(tx_data) * 1.2)
            else:
                tx_data["gas"] = 1500000

        signed_txn = self.web3.eth.account.sign_transaction(
            tx_data, private_key=self.private_key
        )
        tx_token = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)

        # increase nonce
        self.nonce += 1

        return self.web3.to_hex(tx_token)

    def get_susd_balance(self, address: str = None, legacy: bool = False) -> dict:
        """
        Gets current sUSD balance in wallet. Supports both legacy and V3 sUSD.

        :param str address: address to check balances for
        :param bool legacy: check legacy sUSD balance
        :return: A dictionary with the sUSD balance
        :rtype: dict
        """
        # TODO: remove the dictionary return
        if not address:
            address = self.address

        token = self.susd_legacy_token if legacy else self.susd_token
        if token is None:
            return {"balance": 0}

        balance = token.functions.balanceOf(self.address).call()
        return {"balance": wei_to_ether(balance)}

    def get_eth_balance(self, address: str = None) -> dict:
        """
        Gets current ETH and WETH balances at the specified address.

        :param str address: address to check balances for
        :return: A dictionary with the ETH and WETH balances
        :rtype: dict
        """
        if not address:
            address = self.address

        weth_contract = self.web3.eth.contract(
            address=self.contracts["WETH"]["address"], abi=self.contracts["WETH"]["abi"]
        )

        eth_balance = self.web3.eth.get_balance(address)
        weth_balance = weth_contract.functions.balanceOf(address).call()

        return {"eth": wei_to_ether(eth_balance), "weth": wei_to_ether(weth_balance)}

    # transactions
    def approve(
        self,
        token_address: str,
        target_address: str,
        amount: float = None,
        submit: bool = False,
    ):
        """
        Approve an address to spend a specified ERC20 token. This is a general
        implementation that can be used for any ERC20 token. Specify the amount
        as an ether value, otherwise it will default to the maximum amount::

            snx.approve(
                snx.susd_token.address,
                snx.perps.market_proxy.address,
                amount=1000
            )

        :param str token_address: address of the token to approve
        :param str target_address: address to approve to spend the token
        :param float amount: amount of the token to approve
        :param bool submit: submit the transaction
        :return: If ``submit``, returns a transaction hash. Otherwise, returns
            the transaction parameters.
        :rtype: str | dict
        """
        # fix the amount
        amount = 2**256 - 1 if amount is None else ether_to_wei(amount)
        token_contract = self.web3.eth.contract(
            address=token_address, abi=self.contracts["USDProxy"]["abi"]
        )

        tx_params = self._get_tx_params()
        tx_params = token_contract.functions.approve(
            target_address, amount
        ).build_transaction(tx_params)

        if submit:
            tx_hash = self.execute_transaction(tx_params)
            self.logger.info(
                f"Approving {target_address} to spend {amount / 1e18} {token_address} for {self.address}"
            )
            self.logger.info(f"approve tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def allowance(
        self, token_address: str, spender_address: str, owner_address: str = None
    ) -> float:
        """
        Get the allowance for a target address to spend a specified ERC20 token for an owner.
        This is a general implementation that can be used for any ERC20 token.::

            snx.allowance(
                snx.susd_token.address,

                snx.perps.market_proxy.address
            )

        :param str token_address: address of the token to approve
        :param str spender_address: address to spender of the token
        :param str owner_address: address to token owner. If not specified, the default
            address is used.
        :return: The allowance for the target address to spend the token for the owner
        :rtype: float
        """
        if not owner_address:
            owner_address = self.address

        token_contract = self.web3.eth.contract(
            address=token_address, abi=self.contracts["USDProxy"]["abi"]
        )

        allowance = token_contract.functions.allowance(
            owner_address, spender_address
        ).call()

        return wei_to_ether(allowance)

    def wrap_eth(self, amount: float, submit: bool = False) -> str:
        """
        Wraps or unwaps ETH to/from the WETH implementation stored in the constants file.
        Negative numbers will unwrap ETH, positive numbers will wrap ETH::

                snx.wrap_eth(1)
                snx.wrap_eth(-1)

        :param float amount: amount of ETH to wrap
        :param bool submit: submit the transaction
        :return: If ``submit``, returns a transaction hash. Otherwise, returns
            the transaction parameters.
        :rtype: str | dict
        """
        value_wei = ether_to_wei(max(amount, 0))
        weth_contract = self.web3.eth.contract(
            address=self.contracts["WETH"]["address"], abi=self.contracts["WETH"]["abi"]
        )

        if amount < 0:
            fn_name = "withdraw"
            tx_args = [ether_to_wei(abs(amount))]
        else:
            fn_name = "deposit"
            tx_args = []

        tx_params = self._get_tx_params(value=value_wei)
        tx_params = weth_contract.functions[fn_name](*tx_args).build_transaction(
            tx_params
        )

        if submit:
            tx_hash = self.execute_transaction(tx_params)
            self.logger.info(f"Wrapping {amount} ETH for {self.address}")
            self.logger.info(f"wrap_eth tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params
