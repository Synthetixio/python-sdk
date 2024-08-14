import argparse
import logging
import warnings
from web3 import Web3
from web3.constants import ADDRESS_ZERO
from web3.types import TxParams
from .constants import (
    DEFAULT_NETWORK_ID,
    DEFAULT_TRACKING_CODE,
    DEFAULT_SLIPPAGE,
    DEFAULT_GAS_MULTIPLIER,
    DEFAULT_GQL_ENDPOINT_PERPS,
    DEFAULT_GQL_ENDPOINT_RATES,
    DEFAULT_PRICE_SERVICE_ENDPOINT,
    DEFAULT_REFERRER,
    DEFAULT_TRACKING_CODE,
)
from .utils import wei_to_ether, ether_to_wei
from .contracts import load_contracts
from .pyth import Pyth
from .core import Core
from .perps import PerpsV3, BfPerps
from .spot import Spot

from .queries import Queries

warnings.filterwarnings("ignore")


def setup_logging(debug: bool, verbose: int):
    if debug:
        log_level = logging.DEBUG
    elif verbose >= 2:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    # set up logging
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    if not logger.handlers:
        logger.addHandler(handler)
    return logger


def parse_args():
    parser = argparse.ArgumentParser(description="Synthetix SDK")
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv, -vvv)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    # Add this line to handle the case when no arguments are provided
    args, _ = parser.parse_known_args()

    return args


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
    :param str op_mainnet_rpc: An Optimism mainnet RPC endpoint to use for the provider that
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
    :param list perps_disabled_markets: A list of market ids to disable for perps
        trading. This is useful for disabling markets that are deprecated, or to
        limit the number of markets available for trading.
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
    :param int pyth_cache_ttl: Time to live for Pyth cache in seconds.
    :param float gas_multiplier: Multiplier for gas estimates. This is used
        to increase the gas limit for transactions.
    :param bool is_fork: Set to true if the chain is a fork. This will improve
        the way price data is handled by requesting at the block timestamp.

    :return: Synthetix class instance
    :rtype: Synthetix
    """

    def __init__(
        self,
        provider_rpc: str,
        op_mainnet_rpc: str = "https://optimism.llamarpc.com",
        ipfs_gateway: str = "https://ipfs.synthetix.io/ipfs/",
        address: str = ADDRESS_ZERO,
        private_key: str = None,
        network_id: int = None,
        core_account_id: int = None,
        perps_account_id: int = None,
        perps_disabled_markets: list = None,
        tracking_code: str = DEFAULT_TRACKING_CODE,
        referrer: str = DEFAULT_REFERRER,
        max_price_impact: float = DEFAULT_SLIPPAGE,
        use_estimate_gas: bool = True,
        cannon_config: dict = None,
        gql_endpoint_perps: str = None,
        gql_endpoint_rates: str = None,
        satsuma_api_key: str = None,
        price_service_endpoint: str = None,
        pyth_cache_ttl: int = 60,
        gas_multiplier: float = DEFAULT_GAS_MULTIPLIER,
        is_fork: bool = False,
        request_kwargs: dict = {},
    ):
        args = parse_args()
        self.logger = setup_logging(args.debug, args.verbose)

        # init account variables
        self.private_key = private_key
        self.use_estimate_gas = use_estimate_gas
        self.cannon_config = cannon_config
        self.provider_rpc = provider_rpc
        self.op_mainnet_rpc = op_mainnet_rpc
        self.ipfs_gateway = ipfs_gateway
        self.gas_multiplier = gas_multiplier
        self.max_price_impact = max_price_impact
        self.tracking_code = tracking_code
        self.referrer = referrer
        self.is_fork = is_fork

        # init chain provider
        if provider_rpc.startswith("http"):
            web3 = Web3(
                Web3.HTTPProvider(self.provider_rpc, request_kwargs=request_kwargs)
            )
        elif provider_rpc.startswith("wss"):
            web3 = Web3(Web3.WebsocketProvider(self.provider_rpc))
        elif provider_rpc.endswith("ipc"):
            web3 = Web3(Web3.IPCProvider(self.provider_rpc))
        else:
            raise Exception("Provider RPC endpoint is invalid")

        # check for RPC signers
        try:
            self.rpc_signers = web3.eth.accounts
        except Exception as e:
            self.logger.error(f"Error getting RPC signers: {e}")
            self.rpc_signers = []

        if address == ADDRESS_ZERO and len(self.rpc_signers) > 0:
            self.address = self.rpc_signers[0]
            self.logger.info(f"Using RPC signer: {self.address}")
        elif address in self.rpc_signers:
            self.address = address
            self.logger.info(f"Using RPC signer: {self.address}")
        elif address == ADDRESS_ZERO and self.private_key is not None:
            self.address = web3.eth.account.from_key(self.private_key).address
            self.logger.info(f"Using private key signer: {self.address}")
        elif address != ADDRESS_ZERO and self.private_key is not None:
            # check the address matches the private key
            if web3.eth.account.from_key(self.private_key).address != address:
                raise Exception("Private key does not match the provided address")
            self.address = address
            self.logger.info(f"Using private key signer: {self.address}")
        else:
            # set address without private key
            self.address = address
            self.logger.info(
                f"Using provided address without private key: {self.address}"
            )

        # check network id
        if network_id is None:
            self.logger.info(
                f"Setting network_id from RPC chain_id: {web3.eth.chain_id}"
            )
            network_id = web3.eth.chain_id
        elif web3.eth.chain_id != network_id:
            raise Exception("The RPC `chain_id` must match the stored `network_id`")
        else:
            network_id = int(network_id)

        # set nonce
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
        if not price_service_endpoint:
            price_service_endpoint = DEFAULT_PRICE_SERVICE_ENDPOINT

        self.pyth = Pyth(
            self,
            cache_ttl=pyth_cache_ttl,
            price_service_endpoint=price_service_endpoint,
        )
        self.core = Core(self, core_account_id)
        self.spot = Spot(self)

        if "bfp_market_factory" in self.contracts:
            self.perps = BfPerps(self, perps_account_id)
        else:
            self.perps = PerpsV3(self, perps_account_id)

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
        if "system" in self.contracts:
            susd_definition = self.contracts["system"]["USDProxy"]
            susd_address = w3.to_checksum_address(susd_definition["address"])

            susd_token = w3.eth.contract(susd_address, abi=susd_definition["abi"])
        else:
            susd_token = None

        # load multicall contract
        if (
            "system" in self.contracts
            and "trusted_multicall_forwarder" in self.contracts["system"]
        ):
            mc_definition = self.contracts["system"]["trusted_multicall_forwarder"][
                "TrustedMulticallForwarder"
            ]
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

    def _send_transaction(self, tx_data: dict):
        """
        Send a prepared transaction to the connected RPC. If the RPC has a signer for
        the account in the `from` field, the transaction is sent directly to the RPC.
        For other addresses, if a private key is provided, the transaction is signed
        and sent to the RPC. Otherwise, this function will raise an error.

        :param dict tx_data: transaction data
        :return: A transaction hash
        :rtype: str
        """

        is_rpc_signer = tx_data["from"] in self.rpc_signers
        if not is_rpc_signer and self.private_key is None:
            raise Exception("No private key specified.")

        if is_rpc_signer:
            tx_hash = self.web3.eth.send_transaction(tx_data)
        else:
            signed_txn = self.web3.eth.account.sign_transaction(
                tx_data, private_key=self.private_key
            )
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)

        self.nonce += 1
        return self.web3.to_hex(tx_hash)

    def execute_transaction(self, tx_data: dict, reset_nonce: bool = False):
        """
        Execute a provided transaction. This function will be signed with the provided
        private key and submitted to the connected RPC. The ``Synthetix`` object tracks
        the nonce internally, and will handle estimating gas limits if they are not
        provided.

        :param dict tx_data: transaction data
        :param bool reset_nonce: call the RPC to get the current nonce, otherwise use the
            stored nonce
        :return: A transaction hash
        :rtype: str
        """
        if "gas" not in tx_data:
            if self.use_estimate_gas:
                tx_data["gas"] = int(
                    self.web3.eth.estimate_gas(tx_data) * self.gas_multiplier
                )
            else:
                tx_data["gas"] = 1500000

        if reset_nonce:
            self.nonce = self.web3.eth.get_transaction_count(self.address)
            tx_data["nonce"] = self.nonce

        try:
            self.logger.debug(f"Tx data: {tx_data}")
            tx_hash = self._send_transaction(tx_data)
            return tx_hash
        except ValueError as e:
            if "nonce too low" in str(e):
                self.logger.warning("Nonce too low, resetting nonce and retrying.")
                return self.execute_transaction(tx_data, reset_nonce=True)
            else:
                raise Exception(f"Transaction failed: {e}")

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
            address=token_address, abi=self.contracts["common"]["ERC20"]["abi"]
        )

        tx_params = self._get_tx_params()

        # reset nonce on internal transactions
        self.nonce = self.web3.eth.get_transaction_count(self.address)
        tx_params["nonce"] = self.nonce

        # simulate the transaction
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
            address=token_address, abi=self.contracts["common"]["ERC20"]["abi"]
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
        weth_contract = self.contracts["WETH"]["contract"]

        if amount < 0:
            fn_name = "withdraw"
            tx_args = [ether_to_wei(abs(amount))]
        else:
            fn_name = "deposit"
            tx_args = []

        tx_params = self._get_tx_params(value=value_wei)

        # reset nonce on internal transactions
        self.nonce = self.web3.eth.get_transaction_count(self.address)
        tx_params["nonce"] = self.nonce

        # simulate the transaction
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
