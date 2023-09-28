"""Module for interacting with Synthetix V3 spot markets."""
from ..utils import ether_to_wei, wei_to_ether
from ..utils.multicall import write_erc7412
from .constants import SPOT_MARKETS_BY_ID, SPOT_MARKETS_BY_NAME
from typing import Literal
import time
import requests

class Spot:
    """Class for interacting with Synthetix V3 spot markets."""
    def __init__(self, snx, pyth):
        self.snx = snx
        self.pyth = pyth
        self.logger = snx.logger

        # check if spot is deployed on this network
        if 'SpotMarketProxy' in snx.contracts:
            market_proxy_address, market_proxy_abi = snx.contracts[
                'SpotMarketProxy']['address'], snx.contracts['SpotMarketProxy']['abi']

            self.market_proxy = snx.web3.eth.contract(
                address=market_proxy_address, abi=market_proxy_abi)

    # internals
    def _resolve_market(self, market_id: int, market_name: str):
        """Resolve a market_id or market_name to a market_id and market_name"""
        if market_id is None and market_name is None:
            raise ValueError("Must provide a market_id or market_name")

        has_market_id = market_id is not None
        has_market_name = market_name is not None

        if not has_market_id and has_market_name:
            if market_name not in SPOT_MARKETS_BY_NAME[self.snx.network_id]:
                raise ValueError("Invalid market_name")
            market_id = SPOT_MARKETS_BY_NAME[self.snx.network_id][market_name]

            if market_id == -1:
                raise ValueError("Invalid market_name")
        elif has_market_id and not has_market_name:
            if market_id not in SPOT_MARKETS_BY_ID[self.snx.network_id]:
                raise ValueError("Invalid market_id")
            market_name = SPOT_MARKETS_BY_ID[self.snx.network_id][market_id]
        return market_id, market_name

    def _get_synth_contract(self, market_id: int = None, market_name: str = None):
        """Create a contract instance for a specified synth"""
        market_id, market_name = self._resolve_market(market_id, market_name)

        if market_id == 0:
            market_implementation = self.snx.contracts['USDProxy']['address']
        else:
            market_implementation = self.market_proxy.functions.getSynth(market_id).call()

        return self.snx.web3.eth.contract(
            address=market_implementation,
            abi=self.snx.contracts['USDProxy']['abi'],
        )

    # read
    def get_balance(self, address: str = None, market_id: int = None, market_name: str = None):
        """Get the balance of a spot synth"""
        market_id, market_name = self._resolve_market(market_id, market_name)

        if address is None:
            address = self.snx.address

        synth_contract = self._get_synth_contract(market_id)
        balance = synth_contract.functions.balanceOf(address).call()
        return wei_to_ether(balance)

    def get_allowance(self, target_address: str, address: str = None, market_id: int = None, market_name: str = None):
        """Get the allowance for a spot synth for a specified address"""
        market_id, market_name = self._resolve_market(market_id, market_name)

        if address is None:
            address = self.snx.address

        synth_contract = self._get_synth_contract(market_id)
        allowance = synth_contract.functions.allowance(address, target_address).call()
        return wei_to_ether(allowance)

    def get_settlement_strategy(self, settlement_strategy_id: int, market_id: int = None, market_name: str = None):
        """Get the settlement strategy of a market"""
        market_id, market_name = self._resolve_market(market_id, market_name)
        (
            strategy_type,
            settlement_delay,
            settlement_window_duration,
            price_verification_contract,
            feed_id,
            url,
            settlement_reward,
            minimum_usd_exchange_amount,
            max_rounding_loss,
            disabled,
        ) = self.market_proxy.functions.getSettlementStrategy(market_id, settlement_strategy_id).call()
        return {
            "strategy_type": strategy_type,
            "settlement_delay": settlement_delay,
            "settlement_window_duration": settlement_window_duration,
            "price_verification_contract": price_verification_contract,
            "feed_id": feed_id,
            "url": url,
            "settlement_reward": settlement_reward,
            "minimum_usd_exchange_amount": minimum_usd_exchange_amount,
            "max_rounding_loss": max_rounding_loss,
            "disabled": disabled,
        }

    def get_order(self, async_order_id: int, market_id: int = None, market_name: str = None, fetch_settlement_strategy: bool = True):
        """Get an order for a specified async order claim id"""
        market_id, market_name = self._resolve_market(market_id, market_name)

        market_contract = self.market_proxy
        order = market_contract.functions.getAsyncOrderClaim(market_id, async_order_id).call()
        id, owner, order_type, amount_escrowed, settlement_strategy_id, settlement_time, minimum_settlement_amount, settled_at, referrer = order

        order_data = {
            'id': id,
            'owner': owner,
            'order_type': order_type,
            'amount_escrowed': amount_escrowed,
            'settlement_strategy_id': settlement_strategy_id,
            'settlement_time': settlement_time,
            'minimum_settlement_amount': minimum_settlement_amount,
            'settled_at': settled_at,
            'referrer': referrer,
        }

        if fetch_settlement_strategy:
            settlement_strategy = self.get_settlement_strategy(
                settlement_strategy_id, market_id=market_id)
            order_data['settlement_strategy'] = settlement_strategy
        
        return order_data

    # transactions
    # TODO: cancel order
    def approve(
        self,
        target_address: str,
        amount: int = None,
        market_id: int = None,
        market_name: str = None,
        submit: bool = False
    ):
        """Approve an address to spend a spot synth"""
        market_id, market_name = self._resolve_market(market_id, market_name)

        # fix the amount
        amount = 2**256 - 1 if amount is None else ether_to_wei(amount)
        synth_contract = self._get_synth_contract(market_id)
        tx_data = synth_contract.encodeABI(fn_name='approve', args=[
            target_address, amount])

        tx_params = self.snx._get_tx_params()
        tx_params = synth_contract.functions.approve(
            target_address, amount).build_transaction(tx_params)

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Approving {target_address} to spend {amount / 1e18} {market_name}")
            self.logger.info(f"approve tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def commit_order(
        self,
        side: Literal['buy', 'sell'],
        size: int,
        settlement_strategy_id: int = 2,
        market_id: int = None,
        market_name: str = None,
        submit: bool = False,
    ):
        """Commit an order to the spot market"""
        market_id, market_name = self._resolve_market(market_id, market_name)
        # TODO: Add a slippage parameter
        # TODO: Allow user to specify USD or ETH values (?)

        size_wei = ether_to_wei(size)
        order_type = 3 if side == 'buy' else 4

        # prepare the transaction
        tx_args = [
            market_id,              # marketId
            order_type,             # orderType
            size_wei,               # amountProvided
            settlement_strategy_id, # settlementStrategyId
            0,                      # minimumSettlementAmount
            self.snx.referrer,      # referrer
        ]
        tx_params = write_erc7412(
            self.snx, self.market_proxy, 'commitOrder', tx_args)

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Committing {side} order of size {size_wei} ({size}) to {market_name} (id: {market_id})")
            self.logger.info(f"commit_order tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def settle_pyth_order(self, async_order_id: int, market_id: int = None, market_name: str = None, max_retry: int = 10, retry_delay: int = 2, submit: bool = False):
        """Settle a pyth order"""
        # TODO: Update this for spot market
        market_id, market_name = self._resolve_market(market_id, market_name)

        order = self.get_order(async_order_id, market_id=market_id)
        settlement_strategy = order['settlement_strategy']

        # check if order is ready to be settled
        self.logger.info(f"settlement time: {order['settlement_time']}")
        self.logger.info(f"current time: {time.time()}")
        if order['settlement_time'] > time.time():
            duration = order['settlement_time'] - time.time()
            self.logger.info(
                f'Waiting {duration} seconds until order can be settled')
            time.sleep(duration)
        else:
            # TODO: check if expired
            self.logger.info('Order is ready to be settled')

        # create hex inputs
        feed_id_hex = settlement_strategy['feed_id'].hex()
        settlement_time_hex = self.snx.web3.to_hex(
            (order['settlement_time']).to_bytes(8, byteorder='big'))

        # Concatenate the hex strings with '0x' prefix
        data_param = f'0x{feed_id_hex}{settlement_time_hex[2:]}'

        # query pyth for the price update data
        url = settlement_strategy['url'].format(data=data_param)

        retry_count = 0
        price_update_data = None
        while not price_update_data and retry_count < max_retry:
            response = requests.get(url)

            if response.status_code == 200:
                response_json = response.json()
                price_update_data = response_json['data']
            else:
                retry_count += 1
                if retry_count > max_retry:
                    raise ValueError("Price update data not available")

                self.logger.info(
                    "Price update data not available, waiting 2 seconds and retrying")
                time.sleep(retry_delay)

        # encode the extra data
        market_bytes = market_id.to_bytes(32, byteorder='big')
        order_id_bytes = order['id'].to_bytes(32, byteorder='big')

        # Concatenate the bytes and convert to hex
        extra_data = self.snx.web3.to_hex(market_bytes + order_id_bytes)

        # log the data
        self.logger.info(f'price_update_data: {price_update_data}')
        self.logger.info(f'extra_data: {extra_data}')

        # prepare the transaction
        market_proxy = self.market_proxy
        tx_params = write_erc7412(
            self.snx, self.market_proxy, 'settlePythOrder', [price_update_data, extra_data], {'value': 1})

        if submit:
            self.logger.info(f'tx params: {tx_params}')
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Settling order {order['id']}")
            self.logger.info(f"settle tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params
