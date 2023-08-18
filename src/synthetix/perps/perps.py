"""Module for interacting with Synthetix Perps V3."""
from .constants import COLLATERALS_BY_ID, COLLATERALS_BY_NAME, PERPS_MARKETS_BY_ID, PERPS_MARKETS_BY_NAME
from decimal import Decimal
import time
import requests


class Perps:
    """Class for interacting with Synthetix Perps V3 contracts."""
    # TODO: implement asyncio
    # TODO: add waiting for transaction receipt

    def __init__(self, snx, pyth, default_account_id: int = None):
        self.snx = snx
        self.pyth = pyth
        self.logger = snx.logger

        market_proxy_address, market_proxy_abi = snx.contracts[
            'PerpsMarketProxy']['address'], snx.contracts['PerpsMarketProxy']['abi']
        account_proxy_address, account_proxy_abi = snx.contracts[
            'AccountProxy']['address'], snx.contracts['AccountProxy']['abi']

        self.market_proxy = snx.web3.eth.contract(
            address=market_proxy_address, abi=market_proxy_abi)
        self.account_proxy = snx.web3.eth.contract(
            address=account_proxy_address, abi=account_proxy_abi)

        self.account_ids = self.get_account_ids()
        self.markets_by_id, self.markets_by_name = self.get_markets()

        if default_account_id:
            self.default_account_id = default_account_id
        else:
            self.default_account_id = self.account_ids[0]

    # internals
    def _resolve_market(self, market_id: int, market_name: str, collateral: bool = False):
        """Resolve a market_id or market_name to a market_id and market_name"""
        if market_id is None and market_name is None:
            raise ValueError("Must provide a market_id or market_name")

        ID_LOOKUP = COLLATERALS_BY_ID if collateral else PERPS_MARKETS_BY_ID
        NAME_LOOKUP = COLLATERALS_BY_NAME if collateral else PERPS_MARKETS_BY_NAME

        has_market_id = market_id is not None
        has_market_name = market_name is not None

        if not has_market_id and has_market_name:
            if market_name not in NAME_LOOKUP:
                raise ValueError("Invalid market_name")
            market_id = NAME_LOOKUP[market_name]

            if market_id == -1:
                raise ValueError("Invalid market_name")
        elif has_market_id and not has_market_name:
            if market_id not in ID_LOOKUP:
                raise ValueError("Invalid market_id")
            market_name = ID_LOOKUP[market_id]
        return market_id, market_name

    # read
    # TODO: get_market_settings
    def get_markets(self):
        """Get all markets and their market summaries"""
        market_ids = self.market_proxy.functions.getMarkets().call()

        # TODO: add multicall
        raw_market_summaries = [self.market_proxy.functions.getMarketSummary(id).call() for id in market_ids]
        market_summaries = []
        for id_ind, summary in enumerate(raw_market_summaries):
            skew, size, max_open_interest, current_funding_rate, current_funding_velocity, index_price = summary
            market_summaries.append({
                'market_id': market_ids[id_ind],
                'market_name': PERPS_MARKETS_BY_ID[market_ids[id_ind]],
                'skew': skew,
                'size': size,
                'max_open_interest': max_open_interest,
                'current_funding_rate': current_funding_rate,
                'current_funding_velocity': current_funding_velocity,
                'index_price': index_price
            })

        markets_by_id = {
            summary['market_id']: summary
            for summary in market_summaries
        }
        markets_by_name = {
            summary['market_name']: summary
            for summary in market_summaries
        }
        return markets_by_id, markets_by_name


    def get_order(self, account_id: int = None, fetch_settlement_strategy: bool = True):
        """Get the open order for an account"""
        if not account_id:
            account_id = self.default_account_id

        order = self.market_proxy.functions.getOrder(account_id).call()
        settlement_time, request = order
        market_id, account_id, size_delta, settlement_strategy_id, acceptable_price, tracking_code, referrer = request

        order_data = {
            'settlement_time': settlement_time,
            'market_id': market_id,
            'account_id': account_id,
            'size_delta': size_delta,
            'settlement_strategy_id': settlement_strategy_id,
            'acceptable_price': acceptable_price,
            'tracking_code': tracking_code,
            'referrer': referrer
        }

        if fetch_settlement_strategy:
            settlement_strategy = self.get_settlement_strategy(
                settlement_strategy_id, market_id=market_id)
            order_data['settlement_strategy'] = settlement_strategy

        return order_data

    def get_market_summary(self, market_id: int = None, market_name: str = None):
        """Get the summary of a market"""
        market_id, market_name = self._resolve_market(market_id, market_name)

        skew, size, max_open_interest, current_funding_rate, current_funding_velocity, index_price = self.market_proxy.functions.getMarketSummary(
            market_id).call()
        return {
            'skew': skew,
            'size': size,
            'max_open_interest': max_open_interest,
            'current_funding_rate': current_funding_rate,
            'current_funding_velocity': current_funding_velocity,
            'index_price': index_price
        }

    def get_settlement_strategy(self, settlement_strategy_id: int, market_id: int = None, market_name: str = None):
        """Get the settlement strategy of a market"""
        market_id, market_name = self._resolve_market(market_id, market_name)

        (
            strategy_type,
            settlement_delay,
            settlement_window_duration,
            price_window_duration,
            price_verification_contract,
            feed_id,
            url,
            settlement_reward,
            price_deviation_tolerance,
            disabled
        ) = self.market_proxy.functions.getSettlementStrategy(market_id, settlement_strategy_id).call()
        return {
            'strategy_type': strategy_type,
            'settlement_delay': settlement_delay,
            'settlement_window_duration': settlement_window_duration,
            'price_window_duration': price_window_duration,
            'price_verification_contract': price_verification_contract,
            'feed_id': feed_id,
            'url': url,
            'settlement_reward': settlement_reward,
            'price_deviation_tolerance': price_deviation_tolerance,
            'disabled': disabled,
        }

    def get_account_ids(self, address: str = None):
        """Get the perps account_ids owned by an account"""
        if not address:
            address = self.snx.address

        balance = self.account_proxy.functions.balanceOf(address).call()
        account_ids = [
            self.account_proxy.functions.tokenOfOwnerByIndex(address, i).call()
            for i in range(balance)
        ]
        return account_ids

    def get_margin_info(self, account_id: int = None):
        """Get the margin balances and requirements for an account"""
        if not account_id:
            account_id = self.default_account_id

        total_collateral_value = self.market_proxy.functions.totalCollateralValue(
            account_id).call()
        available_margin = self.market_proxy.functions.getAvailableMargin(
            account_id).call()
        withdrawable_margin = self.market_proxy.functions.getWithdrawableMargin(
            account_id).call()
        initial_margin_requirement, maintenance_margin_requirement, total_accumulated_liquidation_rewards, max_liquidation_reward = self.market_proxy.functions.getRequiredMargins(
            account_id).call()

        return {
            'total_collateral_value': total_collateral_value,
            'available_margin': available_margin,
            'withdrawable_margin': withdrawable_margin,
            'initial_margin_requirement': initial_margin_requirement,
            'maintenance_margin_requirement': maintenance_margin_requirement,
            'total_accumulated_liquidation_rewards': total_accumulated_liquidation_rewards,
            'max_liquidation_reward': max_liquidation_reward,
        }

    def get_collateral_balances(self, account_id: int = None):
        """Get the collateral balances for an account"""
        if not account_id:
            account_id = self.default_account_id

        collateral_balances = {}
        for market_id in COLLATERALS_BY_ID:
            balance = self.market_proxy.functions.getCollateralAmount(
                account_id, market_id).call()
            collateral_balances[COLLATERALS_BY_ID[market_id]] = balance

        return collateral_balances

    def get_open_position(self, market_id: int = None, market_name: int = None, account_id: int = None):
        """Get the open position for an account"""
        market_id, market_name = self._resolve_market(market_id, market_name)
        if not account_id:
            account_id = self.default_account_id

        pnl, accrued_funding, position_size = self.market_proxy.functions.getOpenPosition(
            account_id, market_id).call()
        return {
            'pnl': pnl,
            'accrued_funding': accrued_funding,
            'position_size': position_size
        }

    # transactions
    def create_account(self, account_id: int = None, submit: bool = False):
        """Create a perps account"""
        if not account_id:
            tx_args = []
        else:
            tx_args = [account_id]

        market_proxy = self.market_proxy
        tx_data = market_proxy.encodeABI(
            fn_name='createAccount', args=tx_args)

        tx_params = self.snx._get_tx_params(
            to=market_proxy.address)
        tx_params['data'] = tx_data

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(f"Creating account for {self.snx.address}")
            self.logger.info(f"create_account tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def modify_collateral(
        self,
        amount: int,
        market_id=None,
        market_name=None,
        account_id: int = None,
        submit: bool = False,
    ):
        """Deposit or withdraw collateral from an account"""
        market_id, market_name = self._resolve_market(
            market_id, market_name, collateral=True)

        if not account_id:
            account_id = self.default_account_id

        # TODO: check approvals
        market_proxy = self.market_proxy
        tx_data = market_proxy.encodeABI(
            fn_name='modifyCollateral', args=[account_id, market_id, amount])

        tx_params = self.snx._get_tx_params(
            to=market_proxy.address)
        tx_params['data'] = tx_data

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Transferring {amount} {market_name} for account {account_id}")
            self.logger.info(f"modify_collateral tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def commit_order(
        self,
        size: int,
        settlement_strategy_id: int = 0,
        market_id=None,
        market_name=None,
        account_id: int = None,
        desired_fill_price: float = None,
        max_price_impact: float = None,
        submit: bool = False,
    ):
        """Commit an order to the orderbook"""
        market_id, market_name = self._resolve_market(market_id, market_name)

        # set acceptable price
        if desired_fill_price and max_price_impact:
            raise ValueError(
                "Cannot set both desired_fill_price and max_price_impact")

        is_short = -1 if size < 0 else 1
        size_wei = self.snx.web3.to_wei(abs(size), 'ether') * is_short

        if desired_fill_price:
            acceptable_price = desired_fill_price
        else:
            # fetch market summary to get index price
            market_summary = self.get_market_summary(market_id)

            if not max_price_impact:
                max_price_impact = self.snx.max_price_impact
            price_impact = Decimal(1 + is_short*max_price_impact/100)
            acceptable_price = int(
                market_summary['index_price'] * price_impact)

        if not account_id:
            account_id = self.default_account_id

        # prepare the transaction
        tx_args = {
            "marketId": market_id,
            "accountId": account_id,
            "sizeDelta": size_wei,
            "settlementStrategyId": settlement_strategy_id,
            "acceptablePrice": acceptable_price,
            "trackingCode": self.snx.tracking_code,
            "referrer": self.snx.referrer
        }

        market_proxy = self.market_proxy
        tx_data = market_proxy.encodeABI(
            fn_name='commitOrder', args=[tx_args])

        tx_params = self.snx._get_tx_params(
            to=market_proxy.address)
        tx_params['data'] = tx_data

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Committing order size {size_wei} to {market_name} ({market_id}) for {self.snx.address}")
            self.logger.info(f"commit_order tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def settle(self, account_id: int = None, submit: bool = False):
        if not account_id:
            account_id = self.default_account_id

        market_proxy = self.market_proxy
        tx_data = market_proxy.encodeABI(
            fn_name='settle', args=[account_id])

        tx_params = self.snx._get_tx_params(
            to=market_proxy.address)
        tx_params['data'] = tx_data

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Settling order for account {account_id}")
            self.logger.info(f"settle tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def settle_pyth_order(self, account_id: int = None, max_retry: int = 10, retry_delay: int = 2, submit: bool = False):
        if not account_id:
            account_id = self.default_account_id

        order = self.get_order(account_id)
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
            self.logger.info(f'Order is ready to be settled')

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
                else:
                    self.logger.info(
                        "Price update data not available, waiting 2 seconds and retrying")
                    time.sleep(retry_delay)

        # encode the extra data
        account_bytes = account_id.to_bytes(32, byteorder='big')
        market_bytes = order['market_id'].to_bytes(32, byteorder='big')

        # Concatenate the bytes and convert to hex
        extra_data = self.snx.web3.to_hex(account_bytes + market_bytes)

        # log the data
        self.logger.info(f'price_update_data: {price_update_data}')
        self.logger.info(f'extra_data: {extra_data}')

        # prepare the transaction
        market_proxy = self.market_proxy
        tx_data = market_proxy.encodeABI(
            fn_name='settlePythOrder', args=[price_update_data, extra_data])

        tx_params = self.snx._get_tx_params(
            to=market_proxy.address, value=1)
        tx_params['data'] = tx_data

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Settling order for account {account_id}")
            self.logger.info(f"settle tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params
