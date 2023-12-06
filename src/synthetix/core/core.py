"""Module for interacting with Synthetix V3 Core."""
from ..utils import ether_to_wei, wei_to_ether
from ..utils.multicall import call_erc7412, multicall_erc7412, write_erc7412
import time
import requests


class Core:
    """Class for interacting with Synthetix V3 core contracts."""

    def __init__(self, snx, pyth, default_account_id: int = None):
        self.snx = snx
        self.pyth = pyth
        self.logger = snx.logger

        # check if perps is deployed on this network
        if "CoreProxy" in snx.contracts:
            self.core_proxy = snx.contracts["CoreProxy"]["contract"]
            self.account_proxy = snx.contracts["AccountProxy"]["contract"]

            try:
                self.get_account_ids()
            except Exception as e:
                self.account_ids = []
                self.logger.warning(f"Failed to fetch core accounts: {e}")

            if default_account_id:
                self.default_account_id = default_account_id
            elif len(self.account_ids) > 0:
                self.default_account_id = self.account_ids[0]
            else:
                self.default_account_id = None

    # read
    def get_usd_token(self):
        """Get the USD token address"""
        usd_token = call_erc7412(self.snx, self.core_proxy, "getUsdToken", [])
        return self.snx.web3.to_checksum_address(usd_token)

    def get_account_ids(self, address: str = None):
        """Get the core account_ids owned by an account"""
        if not address:
            address = self.snx.address

        balance = self.account_proxy.functions.balanceOf(address).call()

        # multicall the account ids
        inputs = [(address, i) for i in range(balance)]

        account_ids = multicall_erc7412(
            self.snx, self.account_proxy, "tokenOfOwnerByIndex", inputs
        )

        self.account_ids = account_ids
        return account_ids

    def get_market_pool(self, market_id: int):
        """Get the information for a pool"""
        pool = self.core_proxy.functions.getMarketPool(market_id).call()
        return pool

    def get_available_collateral(self, token_address: str, account_id: int = None):
        """Get the available collateral for an account"""
        if not account_id:
            account_id = self.default_account_id

        available_collateral = call_erc7412(
            self.snx,
            self.core_proxy,
            "getAccountAvailableCollateral",
            [account_id, token_address],
        )
        return wei_to_ether(available_collateral)

    # write
    def create_account(self, account_id: int = None, submit: bool = False):
        """Create a core account"""
        if not account_id:
            tx_args = []
        else:
            tx_args = [account_id]

        tx_params = self.snx._get_tx_params()
        tx_params = self.core_proxy.functions.createAccount(*tx_args).build_transaction(
            tx_params
        )

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(f"Creating account for {self.snx.address}")
            self.logger.info(f"create_account tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def deposit(
        self,
        token_address: str,
        amount: float,
        account_id: int = None,
        submit: bool = False,
    ):
        """Deposit collateral to a core account"""
        if not account_id:
            account_id = self.default_account_id

        amount_wei = ether_to_wei(amount)

        tx_params = self.snx._get_tx_params()
        tx_params = self.core_proxy.functions.deposit(
            account_id, token_address, amount_wei
        ).build_transaction(tx_params)

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Depositing {amount} {token_address} for account {account_id}"
            )
            self.logger.info(f"deposit tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def withdraw(
        self,
        amount: float,
        token_address: str = None,
        account_id: int = None,
        submit: bool = False,
    ):
        """Deposit collateral to a core account"""
        if not account_id:
            account_id = self.default_account_id

        if not token_address:
            token_address = self.get_usd_token()

        amount_wei = ether_to_wei(amount)

        tx_args = [account_id, token_address, amount_wei]

        tx_params = write_erc7412(self.snx, self.core_proxy, "withdraw", tx_args)

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Withdrawing {amount} {token_address} from account {account_id}"
            )
            self.logger.info(f"withdraw tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def delegate_collateral(
        self,
        token_address: str,
        amount: float,
        pool_id: int,
        leverage: float = 1,
        account_id: int = None,
        submit: bool = False,
    ):
        """Delegate collateral to a pool"""
        if not account_id:
            account_id = self.default_account_id

        amount_wei = ether_to_wei(amount)
        leverage_wei = ether_to_wei(leverage)

        tx_params = write_erc7412(
            self.snx,
            self.core_proxy,
            "delegateCollateral",
            (account_id, pool_id, token_address, amount_wei, leverage_wei),
        )

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Delegating {amount} {token_address} to pool id {pool_id} for account {account_id}"
            )
            self.logger.info(f"delegate tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def mint_usd(
        self,
        token_address: str,
        amount: float,
        pool_id: int,
        account_id: int = None,
        submit: bool = False,
    ):
        """Mint USD against a core account"""
        if not account_id:
            account_id = self.default_account_id

        amount_wei = ether_to_wei(amount)

        tx_params = write_erc7412(
            self.snx,
            self.core_proxy,
            "mintUsd",
            (account_id, pool_id, token_address, amount_wei),
        )

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Minting {amount} sUSD with {token_address} collateral against pool id {pool_id} for account {account_id}"
            )
            self.logger.info(f"mint tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params
