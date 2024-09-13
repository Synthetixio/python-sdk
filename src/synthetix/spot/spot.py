"""Module for interacting with Synthetix V3 spot markets."""

from eth_utils import encode_hex
from ..utils import ether_to_wei, wei_to_ether, format_ether
from ..utils.multicall import multicall_erc7412, write_erc7412
from .constants import DISABLED_MARKETS
from web3.constants import ADDRESS_ZERO
from typing import Literal
import time
import requests


class Spot:
    """
    Class for interacting with Synthetix V3 spot market contracts. Provider methods for
    wrapping and unwrapping assets, approvals, atomic orders, and async orders.

    Use ``get_`` methods to fetch information about balances, allowances, and markets::

        markets_by_id, markets_by_name = snx.perps.get_markets()
        balance = snx.spot.get_balance(market_name='sUSD')
        allowance = snx.spot.get_allowance(snx.spot.market_proxy.address, market_name='sUSD')

    Other methods prepare transactions, and submit them to your RPC::

        wrap_tx_hash = snx.spot.wrap(100, market_name='sUSDC', submit=True)
        unwrap_tx_hash = snx.spot.wrap(-100, market_name='sUSDC', submit=True)
        atomic_buy_tx_hash = snx.spot.atomic_order('buy', 100, market_name='sUSDC', submit=True)

    An instance of this module is available as ``snx.spot``. If you are using a network without
    spot contracts deployed, the contracts will be unavailable and the methods will raise an error.

    The following contracts are required:

        - SpotMarketProxy

    :param Synthetix snx: An instance of the Synthetix class.
    :param Pyth pyth: An instance of the Pyth class.

    :return: An instance of the Spot class.
    :rtype: Spot
    """

    def __init__(self, snx):
        self.snx = snx
        self.logger = snx.logger

        # settings
        self.async_orders_enabled = False
        if snx.network_id in [421614, 42161]:
            self.async_orders_enabled = True

        self.disabled_markets = (
            DISABLED_MARKETS[snx.network_id]
            if snx.network_id in DISABLED_MARKETS
            else []
        )

        # check if spot is deployed on this network
        if "spotFactory" in snx.contracts:
            self.market_proxy = snx.contracts["spotFactory"]["SpotMarketProxy"][
                "contract"
            ]
            self.markets_by_id, self.markets_by_name = self.get_markets()

    # internals
    def _resolve_market(self, market_id: int, market_name: str):
        """
        Look up the market_id and market_name for a market. If only one is provided,
        the other is resolved. If both are provided, they are checked for consistency.

        :param int | None market_id: The id of the market. If not known, provide ``None``.
        :param str | None market_name: The name of the market. If not known, provide ``None``.

        :return: The ``market_id`` and ``market_name`` for the market.
        :rtype: (int, str)
        """

        """Resolve a market_id or market_name to a market_id and market_name"""
        if market_id is None and market_name is None:
            raise ValueError("Must provide a market_id or market_name")

        has_market_id = market_id is not None
        has_market_name = market_name is not None

        if not has_market_id and has_market_name:
            if market_name not in self.markets_by_name:
                raise ValueError(f"Invalid market_name")
            market_id = self.markets_by_name[market_name]["market_id"]

        elif has_market_id and not has_market_name:
            if market_id not in self.markets_by_id:
                raise ValueError("Invalid market_id")
            market_name = self.markets_by_id[market_id]["market_name"]
        return market_id, market_name

    def _get_synth_contract(self, market_id: int = None, market_name: str = None):
        """
        Private method to fetch the underlying synth contract for a market. Synths are
        represented as an ERC20 token, so this is useful to do things like check allowances
        or transfer tokens. This method requires a ``market_id`` or ``market_name`` to be provided.

        :param int | None market_id: The id of the market.
        :param str | None market_name: The name of the market.

        :return: A contract object for the underlying synth.
        :rtype: web3.eth.Contract
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        return self.markets_by_id[market_id]["contract"]

    def _format_size(
        self,
        size: float,
        market_id: int,
    ):
        """
        Format the size of a synth for an order. This is used for synths whose base asset
        does not use 18 decimals. For example, USDC uses 6 decimals, so we need to handle size
        differently from other assets.

        :param float size: The size as an ether value (e.g. 100).
        :param int market_id: The id of the market.

        :return: The formatted size in wei. (e.g. 100 = 100000000000000000000)
        :rtype: int
        """
        market_id, market_name = self._resolve_market(market_id, None)

        # get the wrapper
        collateral_type, _ = self.market_proxy.functions.getWrapper(market_id).call()

        # make the contract
        wrapper_contract = self.snx.web3.eth.contract(
            address=self.snx.web3.to_checksum_address(collateral_type),
            abi=self.snx.contracts["common"]["ERC20"]["abi"],
        )
        decimals = wrapper_contract.functions.decimals().call()

        # format the size
        size_wei = format_ether(size, decimals=decimals)
        return size_wei

    # read
    def get_markets(self):
        """
        Fetches contracts and metadata about all spot markets on the network. This includes
        the market id, synth name, contract address, and the underlying synth contract. Each
        synth is an ERC20 token, so these contracts can be used for transfers and allowances.
        The metadata is also used to simplify interactions in the SDK by mapping market ids
        and names to their metadata::

            >>> snx.spot.wrap(100, market_name='sUSDC', submit=True)

        This will look up the market id for the sUSDC market and use that to wrap 100 USDC into
        sUSDC.

        The market metadata is returned from the method as a tuple of two dictionaries. The first
        is keyed by ``market_id`` and the second is keyed by ``market_name``::

            >>> snx.spot.markets_by_name
            { 'sUSD': {'market_id': 0, 'contract': ...}, ...}

            >>> snx.spot.markets_by_id
            { '0': {'market_name': 'sUSD', 'contract': ...}, ...}

        :return: Market info keyed by ``market_id`` and ``market_name``.
        :rtype: (dict, dict)
        """
        # set some reasonable defaults to avoid infinite loops
        MAX_ITER = 20
        ITEMS_PER_ITER = 5

        global_market_id = 0
        num_iter = 0
        synths = []
        while num_iter < MAX_ITER:
            addresses = multicall_erc7412(
                self.snx,
                self.market_proxy,
                "getSynth",
                range(num_iter * ITEMS_PER_ITER, (num_iter + 1) * ITEMS_PER_ITER),
            )

            new_synths = [
                (i + num_iter * ITEMS_PER_ITER, address)
                for i, address in enumerate(addresses)
                if address != ADDRESS_ZERO
                and (i + num_iter * ITEMS_PER_ITER) not in self.disabled_markets
            ]
            synths.extend(new_synths)

            global_market_id += len(addresses)
            if addresses[-1] == ADDRESS_ZERO:
                break
            else:
                num_iter += 1

        # build dictionaries by id and name
        markets_by_id = {
            0: {
                "market_id": 0,
                "market_name": "sUSD",
                "contract": self.snx.contracts["system"]["USDProxy"]["contract"],
            }
        }

        if self.async_orders_enabled:
            settlement_strategies = self.get_settlement_strategies(
                strategy_id=0, market_ids=[s[0] for s in synths]
            )
        else:
            self.snx.logger.debug(
                f"Async orders not enabled on network {self.snx.network_id}"
            )
            settlement_strategies = {}

        for market_id, address in synths:
            synth_contract = self.snx.web3.eth.contract(
                address=self.snx.web3.to_checksum_address(address),
                abi=self.snx.contracts["common"]["ERC20"]["abi"],
            )
            market_name = synth_contract.functions.symbol().call()
            symbol = market_name[1:]

            if market_id in self.disabled_markets:
                continue

            markets_by_id[market_id] = {
                "market_id": market_id,
                "market_name": market_name,
                "symbol": symbol,
                "contract": synth_contract,
            }
            if market_id in settlement_strategies:
                markets_by_id[market_id]["settlement_strategy"] = settlement_strategies[
                    market_id
                ]

        # update pyth price feed ids
        update_feeds = {
            markets_by_id[market]["symbol"]: markets_by_id[market][
                "settlement_strategy"
            ]["feed_id"]
            for market in markets_by_id
            if "settlement_strategy" in markets_by_id[market]
        }
        self.snx.pyth.update_price_feed_ids(update_feeds)

        markets_by_name = {
            market["market_name"]: {key: market[key] for key in market.keys()}
            for _, market in markets_by_id.items()
        }
        return markets_by_id, markets_by_name

    def get_balance(
        self, address: str = None, market_id: int = None, market_name: str = None
    ):
        """
        Get the balance of a spot synth. Provide either a ``market_id`` or ``market_name``
        to choose the synth.

        :param str | None address: The address to check the balance of. If not provided, the
            current account will be used.
        :param int | None market_id: The id of the market.
        :param str | None market_name: The name of the market.

        :return: The balance of the synth in ether.
        :rtype: float
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        if address is None:
            address = self.snx.address

        synth_contract = self._get_synth_contract(market_id)
        balance = synth_contract.functions.balanceOf(address).call()
        return wei_to_ether(balance)

    def get_allowance(
        self,
        target_address: str,
        address: str = None,
        market_id: int = None,
        market_name: str = None,
    ):
        """
        Get the allowance for a ``target_address`` to transfer from ``address``. Provide either
        a ``market_id`` or ``market_name`` to choose the synth.

        :param str target_address: The address for which to check allowance.
        :param str address: The owner address to check allowance for.
        :param int market_id: The id of the market.
        :param str market_name: The name of the market.

        :return: The allowance in ether.
        :rtype: float
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        if address is None:
            address = self.snx.address

        synth_contract = self._get_synth_contract(market_id)
        allowance = synth_contract.functions.allowance(address, target_address).call()
        return wei_to_ether(allowance)

    def get_settlement_strategy(
        self,
        settlement_strategy_id: int,
        market_id: int = None,
        market_name: str = None,
    ):
        """
        Fetch the settlement strategy for a spot market.

        :param int settlement_strategy_id: The id of the settlement strategy to retrieve.
        :param int market_id: The id of the market.
        :param str market_name: The name of the market.

        :return: The settlement strategy parameters.
        :rtype: dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        (
            strategy_type,
            settlement_delay,
            settlement_window_duration,
            price_verification_contract,
            feed_id,
            url,
            settlement_reward,
            price_deviation_tolerance,
            minimum_usd_exchange_amount,
            max_rounding_loss,
            disabled,
        ) = self.market_proxy.functions.getSettlementStrategy(
            market_id, settlement_strategy_id
        ).call()
        return {
            "strategy_type": strategy_type,
            "settlement_delay": settlement_delay,
            "settlement_window_duration": settlement_window_duration,
            "price_verification_contract": price_verification_contract,
            "feed_id": encode_hex(feed_id),
            "url": url,
            "settlement_reward": wei_to_ether(settlement_reward),
            "price_deviation_tolerance": wei_to_ether(price_deviation_tolerance),
            "minimum_usd_exchange_amount": wei_to_ether(minimum_usd_exchange_amount),
            "max_rounding_loss": wei_to_ether(max_rounding_loss),
            "disabled": disabled,
        }

    def get_settlement_strategies(
        self,
        strategy_id: int,
        market_ids: list[int] = None,
    ):
        """
        Fetch the settlement strategy id for all spot markets.

        :param int settlement_strategy_id: The id of the settlement strategy to retrieve.
        :param int market_id: The ids of the markets.

        :return: The settlement strategy parameters.
        :rtype: dict
        """
        if market_ids is None:
            market_ids = self.markets_by_id.keys()

        # create the inputs
        inputs = [(market_id, strategy_id) for market_id in market_ids]

        settlement_strategies = multicall_erc7412(
            self.snx, self.market_proxy, "getSettlementStrategy", inputs
        )
        market_settlement_strategies = {
            market_ids[ind]: {
                "strategy_type": strategy_type,
                "settlement_delay": settlement_delay,
                "settlement_window_duration": settlement_window_duration,
                "price_verification_contract": price_verification_contract,
                "feed_id": encode_hex(feed_id),
                "url": url,
                "settlement_reward": wei_to_ether(settlement_reward),
                "price_deviation_tolerance": wei_to_ether(price_deviation_tolerance),
                "minimum_usd_exchange_amount": wei_to_ether(
                    minimum_usd_exchange_amount
                ),
                "max_rounding_loss": wei_to_ether(max_rounding_loss),
                "disabled": disabled,
            }
            for ind, (
                strategy_type,
                settlement_delay,
                settlement_window_duration,
                price_verification_contract,
                feed_id,
                url,
                settlement_reward,
                price_deviation_tolerance,
                minimum_usd_exchange_amount,
                max_rounding_loss,
                disabled,
            ) in enumerate(settlement_strategies)
        }
        return market_settlement_strategies

    def get_order(
        self,
        async_order_id: int,
        market_id: int = None,
        market_name: str = None,
        fetch_settlement_strategy: bool = True,
    ):
        """
        Get details about an async order by its ID.

        Retrieves order details like owner, amount escrowed, settlement strategy, etc.
        Can also fetch the full settlement strategy parameters if ``fetch_settlement_strategy``
        is ``True``.

        Requires either a ``market_id`` or ``market_name`` to be provided to resolve the market.

        :param int async_order_id: The ID of the async order to retrieve.
        :param int market_id: The ID of the market.
        :param str market_name: The name of the market.
        :param bool fetch_settlement_strategy: Whether to fetch the full settlement
            strategy parameters. Default is True.

        :return: The order details.
        :rtype: dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        market_contract = self.market_proxy
        order = market_contract.functions.getAsyncOrderClaim(
            market_id, async_order_id
        ).call()
        (
            id,
            owner,
            order_type,
            amount_escrowed,
            settlement_strategy_id,
            commitment_time,
            minimum_settlement_amount,
            settled_at,
            referrer,
        ) = order

        order_data = {
            "id": id,
            "owner": owner,
            "order_type": order_type,
            "amount_escrowed": amount_escrowed,
            "settlement_strategy_id": settlement_strategy_id,
            "commitment_time": commitment_time,
            "minimum_settlement_amount": minimum_settlement_amount,
            "settled_at": settled_at,
            "referrer": referrer,
        }

        if fetch_settlement_strategy:
            settlement_strategy = self.get_settlement_strategy(
                settlement_strategy_id, market_id=market_id
            )
            order_data["settlement_strategy"] = settlement_strategy

        return order_data

    # transactions
    def approve(
        self,
        target_address: str,
        amount: int = None,
        market_id: int = None,
        market_name: str = None,
        submit: bool = False,
    ):
        """
        Approve an address to transfer a specified synth from the connected address.

        Approves the ``target_address`` to transfer up to the ``amount`` from your account.
        If ``amount`` is ``None``, approves the maximum possible amount.

        Requires either a ``market_id`` or ``market_name`` to be provided to resolve the market.

        :param str target_address: The address to approve.
        :param int amount: The amount in ether to approve. Default is max uint256.
        :param int market_id: The ID of the market.
        :param str market_name: The name of the market.
        :param bool submit: Whether to broadcast the transaction.

        :return: The transaction dict if submit=False, otherwise the tx hash.
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        # fix the amount
        amount = 2**256 - 1 if amount is None else ether_to_wei(amount)
        synth_contract = self._get_synth_contract(market_id)

        tx_params = self.snx._get_tx_params()
        tx_params = synth_contract.functions.approve(
            target_address, amount
        ).build_transaction(tx_params)

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Approving {target_address} to spend {amount / 1e18} {market_name}"
            )
            self.logger.info(f"approve tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def atomic_order(
        self,
        side: Literal["buy", "sell"],
        size: int,
        slippage_tolerance: float = 0,
        min_amount_received: int = None,
        market_id: int = None,
        market_name: str = None,
        submit: bool = False,
    ):
        """
        Execute an atomic order on the spot market.

        Atomically executes a buy or sell order for the given size.

        Amounts are transferred directly, no need to settle later. This function
        is useful for swapping sUSDC with sUSD on Base Andromeda contracts. The default
        slippage is set to zero, since sUSDC and sUSD can be swapped 1:1::

            atomic_order("sell", 100, market_name="sUSDC")

        Requires either a ``market_id`` or ``market_name`` to be provided to resolve the market.

        :param Literal["buy", "sell"] side: The side of the order (buy/sell).
        :param int size: The order size in ether.
        :param float slippage_tolerance: The slippage tolerance for the order as a percentage (0.01 = 1%). Default is 0.
        :param int min_amount_received: The minimum amount to receive in ether units. This will override the slippage_tolerance.
        :param int market_id: The ID of the market.
        :param str market_name: The name of the market.
        :param bool submit: Whether to broadcast the transaction.

        :return: The transaction dict if submit=False, otherwise the tx hash.
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        # first check if on Base where USDC and sUSD are 1:1
        if (
            self.snx.network_id in [8453, 84532]
            and market_name == "sUSDC"
            and min_amount_received is None
        ):
            # assume this is a 1:1 swap
            min_amount_received = size
            min_amount_received_wei = ether_to_wei(min_amount_received)
        elif min_amount_received is None:
            # get the asset price
            token_symbol = self.markets_by_id[market_id]["symbol"]
            feed_id = self.snx.pyth.price_feed_ids[token_symbol]

            price_data = self.snx.pyth.get_price_from_ids([feed_id])
            price = price_data["meta"][feed_id]["price"]

            # adjust size for trade side
            if side == "buy":
                trade_size = size / price
            else:
                trade_size = size * price

            # calculate the amount after slippage
            min_amount_received = trade_size * (1 - slippage_tolerance)
            min_amount_received_wei = ether_to_wei(min_amount_received)
        else:
            min_amount_received_wei = ether_to_wei(min_amount_received)

        size_wei = ether_to_wei(size)

        # prepare the transaction
        tx_args = [
            market_id,  # marketId
            size_wei,  # amount provided
            min_amount_received_wei,  # amount received
            self.snx.referrer,  # referrer
        ]
        tx_params = write_erc7412(self.snx, self.market_proxy, side, tx_args)

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Committing {side} atomic order of size {size_wei} ({size}) to {market_name} (id: {market_id})"
            )
            self.logger.info(f"atomic {side} tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def wrap(
        self,
        size: int,
        market_id: int = None,
        market_name: str = None,
        submit: bool = False,
    ):
        """
        Wrap an underlying asset into a synth or unwrap back to the asset.

        Wraps an asset into a synth if size > 0, unwraps if size < 0.
        The default slippage is set to zero, since the synth and asset can be swapped 1:1.::

            wrap(100, market_name="sUSDC")  # wrap 100 USDC into sUSDC
            wrap(-100, market_name="sUSDC") # wrap 100 USDC into sUSDC

        Requires either a ``market_id`` or ``market_name`` to be provided to resolve the market.

        :param int size: The amount of the asset to wrap/unwrap.
        :param int market_id: The ID of the market.
        :param str market_name: The name of the market.
        :param bool submit: Whether to broadcast the transaction.

        :return: The transaction dict if submit=False, otherwise the tx hash.
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        if size < 0:
            side = "unwrap"

            size_wei = ether_to_wei(-size)
            received_wei = self._format_size(-size, market_id=market_id)
        else:
            side = "wrap"
            size_wei = self._format_size(size, market_id=market_id)
            received_wei = ether_to_wei(size)

        # prepare the transaction
        tx_args = [
            market_id,  # marketId
            size_wei,  # amount provided
            received_wei,  # amount received
        ]
        tx_params = write_erc7412(self.snx, self.market_proxy, side, tx_args)

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"{side} of size {size_wei} ({size}) to {market_name} (id: {market_id})"
            )
            self.logger.info(f"{side} tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def commit_order(
        self,
        side: Literal["buy", "sell"],
        size: int,
        slippage_tolerance: float = 0,
        min_amount_received: int = None,
        settlement_strategy_id: int = 0,
        market_id: int = None,
        market_name: str = None,
        submit: bool = False,
    ):
        """
        Commit an async order to the spot market.

        Commits a buy or sell order of the given size. The order will be settled
        according to the settlement strategy.

        Requires either a ``market_id`` or ``market_name`` to be provided to resolve the market.

        :param Literal["buy", "sell"] side: The side of the order (buy/sell).
        :param int size: The order size in ether. If ``side`` is "buy", this is the amount
            of the synth to buy. If ``side`` is "sell", this is the amount of the synth to sell.
        :param float slippage_tolerance: The slippage tolerance for the order as a percentage (0.01 = 1%). Default is 0.
        :param int min_amount_received: The minimum amount to receive in ether units. This will override the slippage_tolerance.
        :param int settlement_strategy_id: The settlement strategy ID. Default 2.
        :param int market_id: The ID of the market.
        :param str market_name: The name of the market.
        :param bool submit: Whether to broadcast the transaction.

        :return: The transaction dict if submit=False, otherwise the tx hash.
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        # get a price
        if min_amount_received is None:
            feed_id = self.markets_by_id[market_id]["settlement_strategy"]["feed_id"]
            settlement_reward = self.markets_by_id[market_id]["settlement_strategy"][
                "settlement_reward"
            ]
            pyth_data = self.snx.pyth.get_price_from_ids([feed_id])
            price = pyth_data["meta"][feed_id]["price"]

            # adjust size for trade side
            if side == "buy":
                trade_size = size / price
            else:
                trade_size = size * price

            # calculate the amount after slippage
            min_amount_received = (
                trade_size * (1 - slippage_tolerance) - settlement_reward
            )
            min_amount_received_wei = ether_to_wei(min_amount_received)
        else:
            min_amount_received_wei = ether_to_wei(min_amount_received)

        size_wei = ether_to_wei(size)
        order_type = 3 if side == "buy" else 4

        # prepare the transaction
        tx_args = [
            market_id,  # marketId
            order_type,  # orderType
            size_wei,  # amountProvided
            settlement_strategy_id,  # settlementStrategyId
            min_amount_received_wei,  # minimumSettlementAmount
            self.snx.referrer,  # referrer
        ]
        tx_params = write_erc7412(self.snx, self.market_proxy, "commitOrder", tx_args)

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Committing {side} order of size {size_wei} ({size}) to {market_name} (id: {market_id})"
            )
            self.logger.info(f"commit_order tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def settle_order(
        self,
        async_order_id: int,
        market_id: int = None,
        market_name: str = None,
        max_tx_tries: int = 5,
        tx_delay: int = 2,
        submit: bool = False,
    ):
        """
        Settle an async Pyth order after price data is available.

        Fetches the price for the order from Pyth and settles the order.
        Retries up to ``max_tx_tries`` times on failure with a delay of ``tx_delay`` seconds.

        Requires either a ``market_id`` or ``market_name`` to be provided to resolve the market.

        :param int async_order_id: The ID of the async order to settle.
        :param int market_id: The ID of the market. (e.g. "ETH")
        :param str market_name: The name of the market.
        :param int max_tx_tries: Max retry attempts if price fetch fails.
        :param int tx_delay: Seconds to wait between retries.
        :param bool submit: Whether to broadcast the transaction.

        :return: The transaction dict if submit=False, otherwise the tx hash.
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        order = self.get_order(async_order_id, market_id=market_id)
        settlement_strategy = order["settlement_strategy"]
        settlement_time = (
            order["commitment_time"] + settlement_strategy["settlement_delay"]
        )
        expiration_time = (
            order["commitment_time"] + settlement_strategy["settlement_window_duration"]
        )
        now_time = (
            time.time()
            if not self.snx.is_fork
            else self.snx.web3.eth.get_block("latest")["timestamp"]
        )

        # check if order is ready to be settled
        if order["settled_at"] > 0:
            raise ValueError(
                f"Order {async_order_id} on market {market_id} is already settled for account"
            )
        elif settlement_time > now_time:
            duration = settlement_time - now_time
            self.logger.info(f"Waiting {round(duration, 4)} seconds")
            time.sleep(duration)
            self.logger.info(
                f"Order {async_order_id} on market {market_id} is ready to be settled"
            )

        elif expiration_time < now_time:
            raise ValueError(
                f"Order {async_order_id} on market {market_id} has expired"
            )
        else:
            self.logger.info(
                f"Order {async_order_id} on market {market_id} is ready to be settled"
            )

        # prepare the transaction
        tx_tries = 0
        while tx_tries < max_tx_tries:
            try:
                tx_params = write_erc7412(
                    self.snx,
                    self.market_proxy,
                    "settleOrder",
                    [market_id, async_order_id],
                )
            except Exception as e:
                self.logger.error(f"settleOrder error: {e}")
                tx_tries += 1
                time.sleep(tx_delay)
                continue

            if submit:
                tx_hash = self.snx.execute_transaction(tx_params)
                self.logger.info(
                    f"Settling order {async_order_id} for market {market_id}"
                )
                self.logger.info(f"settle tx: {tx_hash}")

                receipt = self.snx.wait(tx_hash)
                self.logger.debug(f"settle receipt: {receipt}")

                # check the order
                order = self.get_order(async_order_id, market_id=market_id)
                if order["settled_at"] > 0:
                    self.logger.info(
                        f"Settlement successful for order {async_order_id} on market {market_id}"
                    )
                    return tx_hash

                tx_tries += 1
                if tx_tries > max_tx_tries:
                    raise ValueError("Failed to settle order")
                else:
                    self.logger.info(
                        "Failed to settle order, waiting 2 seconds and retrying"
                    )
                    time.sleep(tx_delay)
            else:
                return tx_params
