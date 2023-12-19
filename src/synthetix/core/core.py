"""Module for interacting with Synthetix V3 Core."""
from ..utils import ether_to_wei, wei_to_ether
from ..utils.multicall import call_erc7412, multicall_erc7412, write_erc7412
import time
import requests


class Core:
    """
    Class for interacting with Synthetix V3 core contracts.

    Provides methods for creating accounts, depositing and delegating
    collateral, minting sUSD, and interacting with liquidity pools.

    Use ``get_`` methods to fetch information about accounts, collateral,
    and pools::

        account_ids = snx.core.get_account_ids()
        usd_token = snx.core.get_usd_token()
        available_collateral = snx.core.get_available_collateral()

    Other methods prepare transactions to create accounts, deposit collateral,
    mint sUSD, etc. and submit them to the user's RPC::

        create_account_tx = snx.core.create_account(submit=True)
        deposit_tx = snx.core.deposit(amount=100, token='USDC', submit=True)
        mint_tx = snx.core.mint_usd(amount=50, submit=True)

    An instance of this module is available as ``snx.core``. If you are using a
    network without core contracts deployed, the contracts will be unavailable and
    the methods will raise an error.

    The following contracts are required:

        - CoreProxy
        - AccountProxy

    :param Synthetix snx: An instance of the Synthetix class
    :param int default_account_id: The default account ID to use

    :return: An instance of the Core class
    :rtype: Core
    """

    def __init__(self, snx, default_account_id: int = None):
        self.snx = snx
        self.logger = snx.logger

        # check if perps is deployed on this network
        if "CoreProxy" in snx.contracts:
            self.core_proxy = snx.contracts["CoreProxy"]["contract"]
            self.account_proxy = snx.contracts["AccountProxy"]["contract"]

            try:
                self.get_account_ids(default_account_id=default_account_id)
            except Exception as e:
                self.account_ids = []
                self.logger.warning(f"Failed to fetch core accounts: {e}")

    # read
    def get_usd_token(self):
        """Get the address of the USD stablecoin token."""
        usd_token = call_erc7412(self.snx, self.core_proxy, "getUsdToken", [])
        return self.snx.web3.to_checksum_address(usd_token)

    def get_account_ids(self, address: str = None, default_account_id: int = None):
        """
        Get the core account IDs owned by an address.

        Fetches the account IDs for the given address by checking the balance of
        the AccountProxy contract, which is an NFT owned by the address.
        If no address is provided, uses the connected wallet address.

        :param str address: The address to get accounts for. Uses connected address if not provided.
        :param int default_account_id: The default account ID to set after fetching.

        :return: A list of account IDs owned by the address.
        :rtype: list
        """
        if not address:
            address = self.snx.address

        balance = self.account_proxy.functions.balanceOf(address).call()

        # multicall the account ids
        inputs = [(address, i) for i in range(balance)]

        account_ids = multicall_erc7412(
            self.snx, self.account_proxy, "tokenOfOwnerByIndex", inputs
        )

        self.account_ids = account_ids
        if default_account_id:
            self.default_account_id = default_account_id
        elif len(self.account_ids) > 0:
            self.default_account_id = self.account_ids[0]
        else:
            self.default_account_id = None
        return account_ids

    def get_available_collateral(self, token_address: str, account_id: int = None):
        """
        Get the available collateral for an account for a specified collateral type
        of ``token_address``.

        Fetches the amount of undelegated collateral available for withdrawal
        for a given token and account.

        :param str token_address: The address of the collateral token.
        :param int account_id: The ID of the account to check. Uses default if not provided.

        :return: The available collateral as an ether value.
        :rtype: float
        """
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
        """
        Create a new Synthetix account on the core system.

        This function will mint an account NFT to the connected address. Each account
        can have separate LP positions.

        :param int account_id: The ID of the new account. If not provided,
            the next available ID will be used.
        :param bool submit: If True, immediately submit the transaction to
            the blockchain. If False, build the transaction but do not submit.

        :return: The transaction hash if submitted, else the unsigned transaction data.
        :rtype: str | dict
        """
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

            # wait for the transaction, then refetch the ids
            self.snx.wait(tx_hash)
            self.get_account_ids()
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
        """
        Deposit collateral into the specified account. In order to deposit,
        the ``token_address`` must be enabled as collateral on the core system.

        Deposits an ``amount`` of ``token`` as collateral into the ``account_id``.

        :param int amount: The amount of tokens to deposit as collateral.
        :param str token: The address of the token to deposit.
        :param int account_id: The ID of the account to deposit into. Uses default if not provided.
        :param bool submit: If True, immediately submit the transaction.

        :return: The transaction hash if submitted, else the unsigned transaction.
        :rtype: str | dict
        """
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
        """
        Withdraw collateral from the specified account. In order to withdraw,
        the account must have undelegated collateral for ``token_address`` and
        must be past the withdrawal delay.

        Withdraws an `amount` of `token` collateral from the `account_id`.

        :param int amount: The amount of tokens to withdraw from the account.
        :param str token: The address of the token to withdraw.
        :param int account_id: The ID of the account to withdraw from. Uses default if not provided.
        :param bool submit: If True, immediately submit the transaction.

        :return: The transaction hash if submitted, else the unsigned transaction.
        :rtype: str | dict
        """
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
        """
        Delegate collateral for an account to a pool. In order to delegate,
        the account must have undelegated collateral for ``token_address`` and
        the pool must be accepting collateral for ``token_address``.

        Delegates an ``amount`` of ``token_address`` collateral to ``pool_id`` with
        ``leverage`` ratio from ``account_id``.

        :param str token_address: The address of the collateral token to delegate.
        :param float amount: The amount of collateral to delegate.
        :param int pool_id: The ID of the pool to delegate to.
        :param float leverage: The leverage ratio, default 1.
        :param int account_id: The account ID. Uses default if not provided.
        :param bool submit: If True, submit the transaction.

        :return: The transaction hash if submitted, else the unsigned transaction
        :rtype: str | dict
        """
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
        """
        Mint sUSD to a core account. In order to mint, the account must have
        capacity to mint given the settings of the pool.

        Mints ``amount`` of sUSD against ``token_address`` collateral in ``pool_id``
        for ``account_id``.

        :param str token_address: The collateral token address.
        :param float amount: The amount of sUSD to mint.
        :param int pool_id: The ID of the pool to mint against.
        :param int account_id: The account ID. Uses default if not provided.
        :param bool submit: If True, submit the transaction.

        :return: The transaction hash if submitted, else the unsigned transaction
        :rtype: str | dict
        """
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
