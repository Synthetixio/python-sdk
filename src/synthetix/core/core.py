"""Module for interacting with Synthetix V3 Core."""
from ..utils import ether_to_wei, wei_to_ether
from ..utils.multicall import call_erc7412, multicall_erc7412
import time
import requests

class Core:
    """Class for interacting with Synthetix V3 core contracts."""
    def __init__(self, snx, pyth, default_account_id: int = None):
        self.snx = snx
        self.pyth = pyth
        self.logger = snx.logger

        # check if perps is deployed on this network
        if 'CoreProxy' in snx.contracts:
            core_proxy_address, core_proxy_abi = snx.contracts['CoreProxy']['address'], snx.contracts['CoreProxy']['abi']
            account_proxy_address, account_proxy_abi = snx.contracts[
                'AccountProxy']['address'], snx.contracts['AccountProxy']['abi']

            self.core_proxy = snx.web3.eth.contract(
                address=core_proxy_address, abi=core_proxy_abi)
            self.account_proxy = snx.web3.eth.contract(
                address=account_proxy_address, abi=account_proxy_abi)

            self.get_account_ids()

            if default_account_id:
                self.default_account_id = default_account_id
            elif len(self.account_ids) > 0:
                self.default_account_id = self.account_ids[0]
            else:
                self.default_account_id = None
    
    # read
    def get_account_ids(self, address: str = None):
        """Get the core account_ids owned by an account"""
        if not address:
            address = self.snx.address

        balance = self.account_proxy.functions.balanceOf(address).call()

        # multicall the account ids
        inputs = [(address, i) for i in range(balance)]

        account_ids = multicall_erc7412(
            self.snx, self.account_proxy, 'tokenOfOwnerByIndex', inputs)

        self.account_ids = account_ids
        return account_ids

    def get_market_pool(self, market_id: int):
        """Get the information for a pool"""
        pool = self.core_proxy.functions.getMarketPool(market_id).call()
        return pool

    # write
    def create_account(self, account_id: int = None, submit: bool = False):
        """Create a core account"""
        if not account_id:
            tx_args = []
        else:
            tx_args = [account_id]

        core_proxy = self.core_proxy
        tx_data = core_proxy.encodeABI(
            fn_name='createAccount', args=tx_args)

        tx_params = self.snx._get_tx_params(
            to=core_proxy.address)
        tx_params['data'] = tx_data

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(f"Creating account for {self.snx.address}")
            self.logger.info(f"create_account tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def deposit(self, amount: int, account_id: int = None, submit: bool = False):
        """Deposit collateral to a core account"""
        if not account_id:
            account_id = self.default_account_id
    
        amount_wei = ether_to_wei(amount)
        
        core_proxy = self.core_proxy
        tx_data = core_proxy.encodeABI(
            fn_name='deposit', args=[account_id, self.snx.contracts['WETH']['address'], amount_wei])        

        tx_params = self.snx._get_tx_params(
            to=core_proxy.address)
        tx_params['data'] = tx_data

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(f"Depositing {amount} WETH for account {account_id}")
            self.logger.info(f"deposit tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params
