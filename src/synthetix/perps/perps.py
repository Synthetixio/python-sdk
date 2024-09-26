"""Modules for interacting with Synthetix Perps."""

import time
from eth_utils import encode_hex, decode_hex
from ..utils import ether_to_wei, wei_to_ether
from ..utils.multicall import (
    call_erc7412,
    multicall_erc7412,
    write_erc7412,
    make_pyth_fulfillment_request,
)
from .constants import DISABLED_MARKETS
from .perps_utils import unpack_bfp_configuration, unpack_bfp_configuration_by_id


class BasePerps:
    def _resolve_market(self, market_id: int, market_name: str):
        """
        Look up the market_id and market_name for a market. If only one is provided,
        the other is resolved. If both are provided, they are checked for consistency.

        :param int | None market_id: The id of the market. If not known, provide `None`.
        :param str | None market_name: The name of the market. If not known, provide `None`.

        :return: The ``market_id`` and ``market_name`` for the market.
        :rtype: (int, str)
        """
        if market_id is None and market_name is None:
            raise ValueError("Must provide a market_id or market_name")

        has_market_id = market_id is not None
        has_market_name = market_name is not None

        if not has_market_id and has_market_name:
            if market_name not in self.markets_by_name:
                raise ValueError("Invalid market_name")
            market_id = self.markets_by_name[market_name]["market_id"]
        elif has_market_id and not has_market_name:
            if market_id not in self.markets_by_id:
                raise ValueError("Invalid market_id")
            market_name = self.markets_by_id[market_id]["market_name"]
        elif has_market_id and has_market_name:
            market_name_lookup = self.markets_by_id[market_id]["market_id"]
            if market_name != market_name_lookup:
                raise ValueError(
                    f"Market name {market_name} does not match market id {market_id}"
                )
        return market_id, market_name

    def get_account_ids(self, address: str = None, default_account_id: int = None):
        """
        Fetch a list of perps ``account_id`` owned by an address. Perps accounts
        are minted as an NFT to the owner's address. The ``account_id`` is the
        token id of the NFTs held by the address.

        :param str | None address: The address to fetch the account ids for. If not provided, the default address is used.
        :return: A list of account ids.
        :rtype: [int]
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

    def create_account(self, account_id: int = None, submit: bool = False):
        """
        Create a perps account. An account NFT is minted to the sender, who
        owns the account.

        :param int | None account_id: Specify the id of the account. If the id already exists,
        :param boolean submit: If ``True``, submit the transaction to the blockchain.

        :return: If `submit`, returns the trasaction hash. Otherwise, returns the transaction.
        :rtype: str | dict
        """
        if not account_id:
            tx_args = []
        else:
            tx_args = [account_id]

        tx_params = write_erc7412(self.snx, self.market_proxy, "createAccount", tx_args)

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


class PerpsV3(BasePerps):
    """
    Class for interacting with Synthetix Perps V3 contracts. Provides methods for
    creating and managing accounts, depositing and withdrawing collateral,
    committing and settling orders, and liquidating accounts.

    Use ``get_`` methods to fetch information about accounts, markets, and orders::

        markets = snx.perps.get_markets()
        open_positions = snx.perps.get_open_positions()

    Other methods prepare transactions, and submit them to your RPC::

        create_tx_hash = snx.perps.create_account(submit=True)
        collateral_tx_hash = snx.perps.modify_collateral(amount=1000, market_name='sUSD', submit=True)
        order_tx_hash = snx.perps.commit_order(size=10, market_name='ETH', desired_fill_price=2000, submit=True)

    An instance of this module is available as ``snx.perps``. If you are using a network without
    perps deployed, the contracts will be unavailable and the methods will raise an error.

    The following contracts are required:

        - PerpsMarketProxy
        - PerpsAccountProxy
        - PythERC7412Wrapper

    :param Synthetix snx: An instance of the Synthetix class.
    :param int | None default_account_id: The default ``account_id`` to use for transactions.
    :param list | None : A list of market ids to disable.

    :return: An instance of the Perps class.
    :rtype: Perps
    """

    def __init__(self, snx, default_account_id: int = None, disabled_markets=None):
        self.snx = snx
        self.logger = snx.logger
        self.erc7412_enabled = True

        if disabled_markets is None and snx.network_id in DISABLED_MARKETS:
            self.disabled_markets = DISABLED_MARKETS[snx.network_id]
        else:
            self.disabled_markets = disabled_markets if disabled_markets else []

        # check if perps is deployed on this network
        if "perpsFactory" in snx.contracts:
            self.market_proxy = snx.contracts["perpsFactory"]["PerpsMarketProxy"][
                "contract"
            ]
            self.account_proxy = snx.contracts["perpsFactory"]["PerpsAccountProxy"][
                "contract"
            ]

            try:
                self.get_account_ids(default_account_id=default_account_id)
            except Exception as e:
                self.account_ids = []
                self.default_account_id = None
                self.logger.warning(f"Failed to fetch perps accounts: {e}")

            try:
                self.get_markets()
            except Exception as e:
                self.logger.warning(f"Failed to fetch markets: {e}")

            # check if multicollateral
            debt_check = self.market_proxy.find_functions_by_name("debt")
            pay_check = self.market_proxy.find_functions_by_name("payDebt")
            if len(debt_check) == 1 and len(pay_check) == 1:
                self.is_multicollateral = True
                snx.logger.info("Multicollateral perps is enabled")
            else:
                self.is_multicollateral = False

    def _prepare_oracle_call(self, market_names: [str] = []):
        """
        Prepare a call to the external node with oracle updates for the specified market names.
        The result can be passed as the first argument to a multicall function to improve performance
        of ERC-7412 calls. If no market names are provided, all markets are fetched. This is useful for
        read functions since the user does not pay gas for those oracle calls, and reduces RPC calls and
        runtime.

        :param [str] market_names: A list of market names to fetch prices for. If not provided, all markets are fetched.
        :return: The address of the oracle contract, the value to send, and the encoded transaction data.
        :rtype: (str, int, str)
        """
        if len(market_names) == 0:
            market_names = [
                self.market_meta[market]["symbol"] for market in self.market_meta
            ]

        # fetch the data from pyth
        filtered_market_names = [
            m for m in market_names if m in self.snx.pyth.price_feed_ids
        ]
        # if no markets, return an empty list
        if len(filtered_market_names) == 0:
            return []

        feed_ids = [
            self.snx.pyth.price_feed_ids[market_name]
            for market_name in filtered_market_names
        ]
        if not self.snx.is_fork:
            pyth_data = self.snx.pyth.get_price_from_ids(feed_ids)
            price_update_data = pyth_data["price_update_data"]
            price_metadata = pyth_data["meta"]
        else:
            # if it's a fork, get the price for the latest block
            # this avoids providing "future" prices to the contract on a fork
            block = self.snx.web3.eth.get_block("latest")

            # set a manual 60 second staleness
            publish_time = block.timestamp - 60
            pyth_data = self.snx.pyth.get_price_from_ids(
                feed_ids, publish_time=publish_time
            )
            price_update_data = pyth_data["price_update_data"]
            price_metadata = pyth_data["meta"]

        # prepare the oracle call
        to, data, _ = make_pyth_fulfillment_request(
            self.snx,
            self.snx.contracts["pyth_erc7412_wrapper"]["PythERC7412Wrapper"]["address"],
            1,  # update type
            feed_ids,
            price_update_data,
            30,  # staleness tolerance
            0,
        )
        value = len(market_names)

        # return this formatted for the multicall
        # set `require_success` to False in this case, since sometimes
        # the wrapper will return an error if the price has already been updated
        return [(to, False, value, data)], price_metadata

    # read
    def get_markets(self):
        """
        Fetch the ids and summaries for all perps markets. Market summaries include
        information about the market's price, open interest, funding rate,
        and skew::

            markets_by_name = {
                'ETH': {
                    'market_id': 100,
                    'market_name': 'ETH',
                    'skew': -15,
                    'size': 100,
                    'max_open_interest': 10000,
                    'current_funding_rate': 0.000182,
                    'current_funding_velocity': 0.00002765,
                    'index_price': 1852.59,
                    ...
                }
                'BTC': {
                    ...
                }
            }

        :return: Market summaries keyed by `market_id` and `market_name`.
        :rtype: (dict, dict)
        """
        market_ids = self.market_proxy.functions.getMarkets().call()

        # filter disabled markets
        market_ids = [
            market_id
            for market_id in market_ids
            if market_id not in self.disabled_markets
        ]

        # fetch and store the metadata
        market_metadata = multicall_erc7412(
            self.snx, self.market_proxy, "metadata", market_ids
        )

        # fetch settlement strategies to get feed_ids
        settlement_strategy_inputs = [(market_id, 0) for market_id in market_ids]
        settlement_strategies = multicall_erc7412(
            self.snx,
            self.market_proxy,
            "getSettlementStrategy",
            settlement_strategy_inputs,
        )

        self.market_meta = {
            market_id: {
                "name": market_metadata[ind][0],
                "symbol": market_metadata[ind][1],
                "feed_id": encode_hex(settlement_strategies[ind][4]),
            }
            for ind, market_id in enumerate(market_ids)
        }

        # update pyth price feed ids
        self.snx.pyth.update_price_feed_ids(
            {
                self.market_meta[market]["symbol"]: self.market_meta[market]["feed_id"]
                for market in self.market_meta
            }
        )

        # fetch the market summaries
        market_summaries = self.get_market_summaries(market_ids)
        markets_by_id = {summary["market_id"]: summary for summary in market_summaries}

        # fetch funding parameters
        funding_parameters = multicall_erc7412(
            self.snx, self.market_proxy, "getFundingParameters", market_ids
        )

        # fetch fees
        fees = multicall_erc7412(
            self.snx, self.market_proxy, "getOrderFees", market_ids
        )

        # fetch max market
        max_market_values = multicall_erc7412(
            self.snx, self.market_proxy, "getMaxMarketValue", market_ids
        )

        # add them to markets by id
        for ind, market_id in enumerate(market_ids):
            markets_by_id[market_id].update(
                {
                    "skew_scale": wei_to_ether(funding_parameters[ind][0]),
                    "max_funding_velocity": wei_to_ether(funding_parameters[ind][1]),
                    "maker_fee": wei_to_ether(fees[ind][0]),
                    "taker_fee": wei_to_ether(fees[ind][1]),
                    "max_market_value": wei_to_ether(max_market_values[ind]),
                }
            )

        # make markets by market name
        markets_by_name = {
            summary["market_name"]: summary for summary in market_summaries
        }
        self.markets_by_id, self.markets_by_name = markets_by_id, markets_by_name
        return markets_by_id, markets_by_name

    def get_order(self, account_id: int = None, fetch_settlement_strategy: bool = True):
        """
        Fetches the open order for an account.
        Optionally fetches the settlement strategy, which can be useful for order settlement and debugging.

        :param int | None account_id: The id of the account. If not provided, the default account is used.
        :param bool | None fetch_settlement_strategy: If ``True``, fetch the settlement strategy information.
        :return: A dictionary with order information.
        :rtype: dict
        """
        if not account_id:
            account_id = self.default_account_id

        order = call_erc7412(self.snx, self.market_proxy, "getOrder", (account_id,))
        commitment_time, request = order
        (
            market_id,
            account_id,
            size_delta,
            settlement_strategy_id,
            acceptable_price,
            tracking_code,
            referrer,
        ) = request

        order_data = {
            "commitment_time": commitment_time,
            "market_id": market_id,
            "account_id": account_id,
            "size_delta": wei_to_ether(size_delta),
            "settlement_strategy_id": settlement_strategy_id,
            "acceptable_price": wei_to_ether(acceptable_price),
            "tracking_code": tracking_code,
            "referrer": referrer,
        }

        if fetch_settlement_strategy:
            settlement_strategy = self.get_settlement_strategy(
                settlement_strategy_id, market_id=market_id
            )
            order_data["settlement_strategy"] = settlement_strategy

        return order_data

    def get_market_summaries(self, market_ids: [int] = []):
        """
        Fetch the market summaries for a list of ``market_id``.

        :param [int] market_ids: A list of market ids to fetch.
        :return: A list of market summaries in the order of the input ``market_ids``.
        :rtype: [dict]
        """
        # TODO: Fetch for market names
        # get fresh prices to provide to the oracle
        if self.erc7412_enabled:
            calls, _ = self._prepare_oracle_call()
        else:
            calls = []

        inputs = [(market_id,) for market_id in market_ids]

        markets = multicall_erc7412(
            self.snx, self.market_proxy, "getMarketSummary", inputs, calls=calls
        )

        interest_rate = call_erc7412(
            self.snx, self.market_proxy, "interestRate", (), calls=calls
        )

        if len(market_ids) != len(markets):
            self.logger.warning("Failed to fetch some market summaries")

        market_summaries = []
        for ind, market in enumerate(markets):
            (
                skew,
                size,
                max_open_interest,
                current_funding_rate,
                current_funding_velocity,
                index_price,
            ) = market
            market_id = market_ids[ind]

            market_summaries.append(
                {
                    "market_id": market_id,
                    "market_name": self.market_meta[market_id]["symbol"],
                    "feed_id": self.market_meta[market_id]["feed_id"],
                    "skew": wei_to_ether(skew),
                    "size": wei_to_ether(size),
                    "max_open_interest": wei_to_ether(max_open_interest),
                    "interest_rate": wei_to_ether(interest_rate),
                    "current_funding_rate": wei_to_ether(current_funding_rate),
                    "current_funding_velocity": wei_to_ether(current_funding_velocity),
                    "index_price": wei_to_ether(index_price),
                }
            )
        return market_summaries

    def get_market_summary(self, market_id: int = None, market_name: str = None):
        """
        Fetch the market summary for a single market, including
        information about the market's price, open interest, funding rate,
        and skew. Provide either the `market_id` or `market_name`.

        :param int | None market_id: A market id to fetch the summary for.
        :param str | None market_name: A market name to fetch the summary for.
        :return: A dictionary with the market summary.
        :rtype: dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        # get a fresh price to provide to the oracle
        if self.erc7412_enabled:
            calls, _ = self._prepare_oracle_call()
        else:
            calls = []

        (
            skew,
            size,
            max_open_interest,
            current_funding_rate,
            current_funding_velocity,
            index_price,
        ) = call_erc7412(
            self.snx, self.market_proxy, "getMarketSummary", market_id, calls=calls
        )

        return {
            "market_id": market_id,
            "market_name": market_name,
            "skew": wei_to_ether(skew),
            "size": wei_to_ether(size),
            "max_open_interest": wei_to_ether(max_open_interest),
            "current_funding_rate": wei_to_ether(current_funding_rate),
            "current_funding_velocity": wei_to_ether(current_funding_velocity),
            "index_price": wei_to_ether(index_price),
        }

    def get_settlement_strategy(
        self,
        settlement_strategy_id: int,
        market_id: int = None,
        market_name: str = None,
    ):
        """
        Fetch the settlement strategy for a market. Settlement strategies describe the
        conditions under which an order can be settled. Provide either a ``market_id``
        or ``market_name``.

        :param int settlement_strategy_id: The id of the settlement strategy to fetch.
        :param int | None market_id: The id of the market to fetch the settlement strategy for.
        :param str | None market_name: The name of the market to fetch the settlement strategy for.
        :return: A dictionary with the settlement strategy information.
        :rtype: dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        (
            strategy_type,
            settlement_delay,
            settlement_window_duration,
            price_verification_contract,
            feed_id,
            settlement_reward,
            disabled,
            commitment_price_delay,
        ) = call_erc7412(
            self.snx,
            self.market_proxy,
            "getSettlementStrategy",
            (market_id, settlement_strategy_id),
        )

        return {
            "strategy_type": strategy_type,
            "settlement_delay": settlement_delay,
            "settlement_window_duration": settlement_window_duration,
            "price_verification_contract": price_verification_contract,
            "feed_id": feed_id,
            "settlement_reward": wei_to_ether(settlement_reward),
            "disabled": disabled,
            "commitment_price_delay": commitment_price_delay,
        }

    def get_margin_info(self, account_id: int = None):
        """
        Fetch information about an account's margin requirements and balances.
        Accounts must maintain an ``available_margin`` above the ``maintenance_margin_requirement``
        to avoid liquidation. Accounts with ``available_margin`` below the ``initial_margin_requirement``
        can not interact with their position unless they deposit more collateral.

        :param int | None account_id: The id of the account to fetch the margin info for. If not provided, the default account is used.
        :return: A dictionary with the margin information.
        :rtype: dict
        """
        if not account_id:
            account_id = self.default_account_id

        # get fresh prices to provide to the oracle
        if self.erc7412_enabled:
            calls, _ = self._prepare_oracle_call()
        else:
            calls = []

        # TODO: expand multicall capability to handle multiple functions
        total_collateral_value = call_erc7412(
            self.snx,
            self.market_proxy,
            "totalCollateralValue",
            (account_id,),
            calls=calls,
        )
        available_margin = call_erc7412(
            self.snx,
            self.market_proxy,
            "getAvailableMargin",
            (account_id,),
            calls=calls,
        )
        withdrawable_margin = call_erc7412(
            self.snx,
            self.market_proxy,
            "getWithdrawableMargin",
            (account_id,),
            calls=calls,
        )
        (
            initial_margin_requirement,
            maintenance_margin_requirement,
            max_liquidation_reward,
        ) = call_erc7412(
            self.snx,
            self.market_proxy,
            "getRequiredMargins",
            (account_id,),
            calls=calls,
        )

        if self.is_multicollateral:
            collateral_ids = call_erc7412(
                self.snx,
                self.market_proxy,
                "getAccountCollateralIds",
                (account_id,),
                calls=calls,
            )
            debt = call_erc7412(
                self.snx,
                self.market_proxy,
                "debt",
                (account_id,),
                calls=calls,
            )

            if len(collateral_ids) == 0:
                collateral_amount_dict = {}
            else:
                collateral_amounts = multicall_erc7412(
                    self.snx,
                    self.market_proxy,
                    "getCollateralAmount",
                    [(account_id, collateral_id) for collateral_id in collateral_ids],
                    calls=calls,
                )
                collateral_amount_dict = {
                    collateral_id: wei_to_ether(amount)
                    for collateral_id, amount in zip(collateral_ids, collateral_amounts)
                }

        else:
            collateral_amount_dict = {0: wei_to_ether(total_collateral_value)}
            debt = 0

        return {
            "total_collateral_value": wei_to_ether(total_collateral_value),
            "collateral_balances": collateral_amount_dict,
            "debt": wei_to_ether(debt),
            "available_margin": wei_to_ether(available_margin),
            "withdrawable_margin": wei_to_ether(withdrawable_margin),
            "initial_margin_requirement": wei_to_ether(initial_margin_requirement),
            "maintenance_margin_requirement": wei_to_ether(
                maintenance_margin_requirement
            ),
            "max_liquidation_reward": wei_to_ether(max_liquidation_reward),
        }

    def get_collateral_balances(self, account_id: int = None):
        """
        Fetch the balance of each collateral type for an account.

        :param int | None account_id: The id of the account to fetch the collateral balances for. If not provided, the default account is used.
        :return: A dictionary with the collateral balances.
        :rtype: dict
        """
        if not account_id:
            account_id = self.default_account_id

        inputs = [(account_id, market_id) for market_id in self.snx.spot.markets_by_id]

        # call for the balances
        balances = multicall_erc7412(
            self.snx, self.market_proxy, "getCollateralAmount", inputs
        )

        # make a clean dictionary
        collateral_balances = {
            self.snx.spot.markets_by_id[inputs[ind][1]]["market_name"]: wei_to_ether(
                balance
            )
            for ind, balance in enumerate(balances)
        }
        return collateral_balances

    def get_can_liquidate(self, account_id: int = None):
        """
        Check if an ``account_id`` is eligible for liquidation.

        :param int | None account_id: The id of the account to check. If not provided, the default account is used.
        :return: A boolean indicating if the account is eligible for liquidation.
        :rtype: bool
        """
        if not account_id:
            account_id = self.default_account_id

        # get fresh prices to provide to the oracle
        if self.erc7412_enabled:
            calls, _ = self._prepare_oracle_call()
        else:
            calls = []

        can_liquidate = call_erc7412(
            self.snx, self.market_proxy, "canLiquidate", account_id, calls=calls
        )

        return can_liquidate

    def get_can_liquidates(self, account_ids: [int] = [None]):
        """
        Check if a batch of ``account_id`` are eligible for liquidation.

        :param [int] account_ids: A list of account ids to check.
        :return: A list of tuples containing the ``account_id`` and a boolean indicating if the account is eligible for liquidation.
        :rtype: [(int, bool)]
        """
        account_ids = [(account_id,) for account_id in account_ids]

        # get fresh prices to provide to the oracle
        if self.erc7412_enabled:
            calls, _ = self._prepare_oracle_call()
        else:
            calls = []

        can_liquidates = multicall_erc7412(
            self.snx, self.market_proxy, "canLiquidate", account_ids, calls=calls
        )

        # combine the results with the account ids, return tuples like (account_id, can_liquidate)
        can_liquidates = [
            (account_ids[ind][0], can_liquidate)
            for ind, can_liquidate in enumerate(can_liquidates)
        ]
        return can_liquidates

    def get_open_position(
        self, market_id: int = None, market_name: int = None, account_id: int = None
    ):
        """
        Fetch the position for a specified account and market. The result includes the unrealized
        pnl since the last interaction with this position, any accrued funding, and the position size.
        Provide either a ``market_id`` or a ``market_name``::

            open_position = {
                'pnl': 86.56,
                'accrued_funding': -10.50,
                'position_size': 10.0,
            }

        :param int | None market_id: The id of the market to fetch the position for.
        :param str | None market_name: The name of the market to fetch the position for.
        :param int | None account_id: The id of the account to fetch the position for. If not provided, the default account is used.
        :return: A dictionary with the position information.
        :rtype: dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if not account_id:
            account_id = self.default_account_id

        # get a fresh price to provide to the oracle
        if self.erc7412_enabled:
            calls, _ = self._prepare_oracle_call([market_name])
        else:
            calls = []

        pnl, accrued_funding, position_size, owed_interest = call_erc7412(
            self.snx,
            self.market_proxy,
            "getOpenPosition",
            (account_id, market_id),
            calls=calls,
        )
        return {
            "pnl": wei_to_ether(pnl),
            "accrued_funding": wei_to_ether(accrued_funding),
            "position_size": wei_to_ether(position_size),
            "owed_interest": wei_to_ether(owed_interest),
        }

    def get_open_positions(
        self,
        market_names: [str] = None,
        market_ids: [int] = None,
        account_id: int = None,
    ):
        """
        Get the open positions for a list of markets.
        Provide either a list of ``market_name`` or ``market_id``::

            open_positions = {
                'ETH': {
                    'market_id': 100,
                    'market_name': 'ETH',
                    'pnl': 86.56,
                    'accrued_funding': -10.50,
                    'position_size': 10.0,
                },
                'BTC': {
                    ...
                }
            }

        :param [str] | None market_names: A list of market names to fetch the positions for.
        :param [int] | None market_ids: A list of market ids to fetch the positions for.
        :param int | None account_id: The id of the account to fetch the positions for. If not provided, the default account is used.
        :return: A dictionary with the position information keyed by ``market_name``.
        :rtype: dict
        """
        if not account_id:
            account_id = self.default_account_id

        # if no market names or ids are provided, fetch all markets
        if not market_names and not market_ids:
            market_ids = list(self.markets_by_id.keys())
            market_names = list(self.markets_by_name.keys())
        elif market_names and not market_ids:
            market_ids = [
                self._resolve_market(None, market_name)[0]
                for market_name in market_names
            ]

        # make the function inputs
        clean_inputs = [(account_id, market_id) for market_id in market_ids]

        # get a fresh price to provide to the oracle
        if self.erc7412_enabled:
            calls, _ = self._prepare_oracle_call(market_names)
        else:
            calls = []

        open_positions = multicall_erc7412(
            self.snx, self.market_proxy, "getOpenPosition", clean_inputs, calls=calls
        )

        open_positions = {
            market_names[ind]: {
                "market_id": market_ids[ind],
                "market_name": market_names[ind],
                "pnl": wei_to_ether(pnl),
                "accrued_funding": wei_to_ether(accrued_funding),
                "owed_interest": wei_to_ether(owedInterest),
                "position_size": wei_to_ether(position_size),
            }
            for ind, (pnl, accrued_funding, position_size, owedInterest) in enumerate(
                open_positions
            )
            if abs(position_size) > 0
        }
        return open_positions

    def get_quote(
        self,
        size: float,
        price: float = None,
        market_id: int = None,
        market_name: str = None,
        account_id: int = None,
        settlement_strategy_id: int = 0,
        include_required_margin: bool = True,
    ):
        """
        Get a quote for the size of an order in a specified market. The quote includes
        the provided price and the fill price of the order after price impact. If a price
        is not provided, a price will be fetched from Pyth. Provide either a ``market_id``
        or ``market_name``.

        :param float size: The size of the order to quote.
        :param float | None price: The price to quote the order at. If not provided, the current market price is used.
        :param int | None market_id: The id of the market to quote the order for.
        :param str | None market_name: The name of the market to quote the order for.
        :param int | None account_id: The id of the account to quote the order for. If not provided, the default account is used.
        :param int settlement_strategy_id: The id of the settlement strategy to use for the settlement reward calculation.
        :param bool include_required_margin: If ``True``, include the required margin for the account in the quote.
        :return: A dictionary with the quote information.
        :rtype: dict
        """
        if not account_id:
            account_id = self.default_account_id

        market_id, market_name = self._resolve_market(market_id, market_name)
        feed_id = self.markets_by_id[market_id]["feed_id"]

        if not price:
            calls, meta = self._prepare_oracle_call([market_name])
            price = meta[feed_id]["price"]
        else:
            calls = []
            price = price

        order_fees, fill_price = call_erc7412(
            self.snx,
            self.market_proxy,
            "computeOrderFeesWithPrice",
            (market_id, ether_to_wei(size), ether_to_wei(price)),
            calls=calls,
        )

        settlement_reward_cost = call_erc7412(
            self.snx,
            self.market_proxy,
            "getSettlementRewardCost",
            (market_id, settlement_strategy_id),
            calls=calls,
        )

        result = {
            "order_size": size,
            "index_price": price,
            "order_fees": wei_to_ether(order_fees),
            "settlement_reward_cost": wei_to_ether(settlement_reward_cost),
            "fill_price": wei_to_ether(fill_price),
        }

        if include_required_margin and account_id:
            required_margin = call_erc7412(
                self.snx,
                self.market_proxy,
                "requiredMarginForOrderWithPrice",
                (account_id, market_id, ether_to_wei(size), ether_to_wei(price)),
                calls=calls,
            )
            result["required_margin"] = wei_to_ether(required_margin)
        return result

    # transactions
    def modify_collateral(
        self,
        amount: int,
        market_id=None,
        market_name=None,
        account_id: int = None,
        submit: bool = False,
    ):
        """
        Move collateral in or out of a specified perps account. The ``market_id``
        or ``market_name`` must be provided to specify the collateral type.
        Provide either a ``market_id`` or a ``market_name``.  Note that the ``market_id``
        here refers to the spot market id, not the perps market id. Make sure to approve
        the market proxy to transfer tokens of the collateral type before calling this function.

        :param int amount: The amount of collateral to move. Positive values deposit collateral, negative values withdraw collateral.
        :param int | None market_id: The id of the market to move collateral for.
        :param str | None market_name: The name of the market to move collateral for.
        :param int | None account_id: The id of the account to move collateral for. If not provided, the default account is used.
        :param bool submit: If ``True``, submit the transaction to the blockchain.
        :return: If ``submit``, returns the trasaction hash. Otherwise, returns the transaction.
        :rtype: str | dict
        """
        market_id, market_name = self.snx.spot._resolve_market(market_id, market_name)

        if not account_id:
            account_id = self.default_account_id

        # TODO: check approvals
        tx_params = write_erc7412(
            self.snx,
            self.market_proxy,
            "modifyCollateral",
            [account_id, market_id, ether_to_wei(amount)],
        )

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Transferring {amount} {market_name} for account {account_id}"
            )
            self.logger.info(f"modify_collateral tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def pay_debt(
        self,
        amount: int = None,
        account_id: int = None,
        submit: bool = False,
    ):
        """
        Pay the debt of a perps account. If no amount is provided, the full debt
        of the account is repaid. Make sure to approve the proxy to transfer sUSD before
        calling this function.

        :param int | None amount: The amount of debt to repay. If not provided, the full debt is repaid.
        :param int | None account_id: The id of the account to repay the debt for. If not provided, the default account is used.
        :param bool submit: If ``True``, submit the transaction to the blockchain.
        :return: If ``submit``, returns the trasaction hash. Otherwise, returns the transaction.
        :rtype: str | dict
        """
        if account_id is None:
            account_id = self.default_account_id

        if amount is None:
            amount = call_erc7412(
                self.snx,
                self.market_proxy,
                "debt",
                (account_id,),
            )
        else:
            amount = ether_to_wei(amount)

        tx_params = write_erc7412(
            self.snx,
            self.market_proxy,
            "payDebt",
            [account_id, amount],
        )
        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(f"Repaying debt of {amount} for account {account_id}")
            self.logger.info(f"payDebt tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def commit_order(
        self,
        size: int,
        settlement_strategy_id: int = 0,
        market_id: int = None,
        market_name: str = None,
        account_id: int = None,
        desired_fill_price: float = None,
        max_price_impact: float = None,
        submit: bool = False,
    ):
        """
        Submit an order to the specified market. Keepers will attempt to fill the order
        according to the settlement strategy. If ``desired_fill_price`` is provided, the order
        will be filled at that price or better. If ``max_price_impact`` is provided, the
        ``desired_fill_price`` is calculated from the current market price and the price impact.

        :param int size: The size of the order to submit.
        :param int settlement_strategy_id: The id of the settlement strategy to use.
        :param int | None market_id: The id of the market to submit the order to. If not provided, `market_name` must be provided.
        :param str | None market_name: The name of the market to submit the order to. If not provided, `market_id` must be provided.
        :param int | None account_id: The id of the account to submit the order for. Defaults to `default_account_id`.
        :param float | None desired_fill_price: The max price for longs and minimum price for shorts. If not provided, one will be calculated based on `max_price_impact`.
        :param float | None max_price_impact: The maximum price impact to allow when filling the order as a percentage (1.0 = 1%). If not provided, it will inherit the default value from `snx.max_price_impact`.
        :param bool submit: If ``True``, submit the transaction to the blockchain.

        :return: If `submit`, returns the trasaction hash. Otherwise, returns the transaction.
        """
        market_id, market_name = self._resolve_market(market_id, market_name)

        # set acceptable price
        if desired_fill_price and max_price_impact:
            raise ValueError("Cannot set both desired_fill_price and max_price_impact")

        is_short = -1 if size < 0 else 1
        size_wei = ether_to_wei(abs(size)) * is_short

        if desired_fill_price:
            acceptable_price = desired_fill_price
        else:
            # fetch market summary to get index price
            market_summary = self.get_market_summary(market_id)

            if not max_price_impact:
                max_price_impact = self.snx.max_price_impact
            price_impact = 1 + is_short * max_price_impact / 100
            # TODO: check that this price is skew-adjusted
            acceptable_price = market_summary["index_price"] * price_impact

        if not account_id:
            account_id = self.default_account_id

        # prepare the transaction
        tx_args = {
            "marketId": market_id,
            "accountId": account_id,
            "sizeDelta": size_wei,
            "settlementStrategyId": settlement_strategy_id,
            "acceptablePrice": ether_to_wei(acceptable_price),
            "trackingCode": self.snx.tracking_code,
            "referrer": self.snx.referrer,
        }

        tx_params = write_erc7412(self.snx, self.market_proxy, "commitOrder", [tx_args])

        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Committing order size {size_wei} ({size}) to {market_name} (id: {market_id}) for account {account_id}"
            )
            self.logger.info(f"commit_order tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def liquidate(
        self, account_id: int = None, submit: bool = False, static: bool = False
    ):
        """
        Submit a liquidation for an account, or static call the liquidation function to fetch
        the liquidation reward. The static call is important for accounts which have been
        partially liquidated. Due to the throughput limit on liquidated value, the static call
        returning a nonzero value means more value can be liquidated (and rewards collected).
        This function can not be called if ``submit`` and ``static`` are true.

        :param int | None account_id: The id of the account to liquidate. If not provided, the default account is used.
        :param bool submit: If ``True``, submit the transaction to the blockchain.
        :param bool static: If ``True``, static call the liquidation function to fetch the liquidation reward.
        :return: If ``submit``, returns the trasaction hash. If ``static``, returns the liquidation reward. Otherwise, returns the transaction.
        :rtype: str | dict | float
        """
        if not account_id:
            account_id = self.default_account_id

        if submit and static:
            raise ValueError("Cannot submit and use static in the same transaction")

        market_proxy = self.market_proxy
        if static:
            liquidation_reward = call_erc7412(
                self.snx, market_proxy, "liquidate", [account_id]
            )

            return wei_to_ether(liquidation_reward)
        else:
            tx_params = write_erc7412(self.snx, market_proxy, "liquidate", [account_id])

            if submit:
                tx_hash = self.snx.execute_transaction(tx_params)
                self.logger.info(f"Liquidating account {account_id}")
                self.logger.info(f"liquidate tx: {tx_hash}")
                return tx_hash
            else:
                return tx_params

    def settle_order(
        self,
        account_id: int = None,
        submit: bool = False,
        max_tx_tries: int = 3,
        tx_delay: int = 2,
    ):
        """
        Settles an order using ERC7412 by handling ``OracleDataRequired`` errors and forming a multicall.
        If the order is not yet ready to be settled, this function will wait until the settlement time.
        If the transaction fails, this function will retry until the max number of tries is reached with a
        configurable delay.

        :param int | None account_id: The id of the account to settle. If not provided, the default account is used.
        :param bool submit: If ``True``, submit the transaction to the blockchain.
        :param int max_tx_tries: The max number of tries to submit the transaction.
        :param int tx_delay: The delay in seconds between transaction submissions.
        """
        if not account_id:
            account_id = self.default_account_id

        order = self.get_order(account_id)
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
        if order["size_delta"] == 0:
            raise ValueError(f"Order is already settled for account {account_id}")
        elif settlement_time > now_time:
            duration = settlement_time - now_time
            self.logger.info(f"Waiting {round(duration, 4)} seconds to settle order")
            time.sleep(duration)
        elif expiration_time < now_time:
            raise ValueError(f"Order has expired for account {account_id}")
        else:
            self.logger.info(f"Order is ready to be settled")

        # get fresh prices to provide to the oracle
        market_name = self._resolve_market(order["market_id"], None)[1]
        # prepare the transaction
        tx_tries = 0
        while tx_tries < max_tx_tries:
            try:
                tx_params = write_erc7412(
                    self.snx,
                    self.market_proxy,
                    "settleOrder",
                    [account_id],
                )
            except Exception as e:
                self.logger.error(f"settleOrder error: {e}")
                tx_tries += 1
                time.sleep(tx_delay)
                continue

            if submit:
                tx_hash = self.snx.execute_transaction(tx_params)
                self.logger.info(f"Settling order for account {account_id}")
                self.logger.info(f"settle tx: {tx_hash}")

                receipt = self.snx.wait(tx_hash)
                self.logger.debug(f"settle receipt: {receipt}")

                # check the order
                order = self.get_order(account_id)
                if order["size_delta"] == 0:
                    self.logger.info(
                        f"Order settlement successful for account {account_id}"
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


class BfPerps(BasePerps):
    """
    Class for interacting with Synthetix Perps contracts on L1. Provides methods for
    creating and managing accounts, depositing and withdrawing collateral,
    committing and settling orders, and liquidating accounts.

    Use ``get_`` methods to fetch information about accounts, markets, and orders::

        markets = snx.perps.get_markets()
        open_positions = snx.perps.get_open_positions()

    Other methods prepare transactions, and submit them to your RPC::

        create_tx_hash = snx.perps.create_account(submit=True)
        collateral_tx_hash = snx.perps.modify_collateral(amount=1000, market_name='sUSD', submit=True)
        order_tx_hash = snx.perps.commit_order(size=10, market_name='ETH', desired_fill_price=2000, submit=True)

    An instance of this module is available as ``snx.perps``. If you are using a network without
    perps deployed, the contracts will be unavailable and the methods will raise an error.

    The following contracts are required:

        - PerpsMarketProxy
        - PerpsAccountProxy
        - PythERC7412Wrapper

    :param Synthetix snx: An instance of the Synthetix class.
    :param Pyth pyth: An instance of the Pyth class.
    :param int | None default_account_id: The default ``account_id`` to use for transactions.

    :return: An instance of the Perps class.
    :rtype: Perps
    """

    def __init__(self, snx, default_account_id: int = None):
        self.snx = snx
        self.logger = snx.logger

        # check if perps is deployed on this network

        if "bfp_market_factory" in snx.contracts:
            self.market_proxy = snx.contracts["bfp_market_factory"]["BfpMarketProxy"][
                "contract"
            ]
            self.account_proxy = snx.contracts["bfp_market_factory"][
                "PerpAccountProxy"
            ]["contract"]

            try:
                self.get_account_ids(default_account_id=default_account_id)
            except Exception as e:
                self.account_ids = []
                self.default_account_id = None
                self.logger.warning(f"Failed to fetch perps accounts: {e}")

            try:
                self.get_markets()
                pass
            except Exception as e:
                self.logger.warning(f"Failed to fetch markets: {e}")

    def get_markets(self):
        """
        Fetch the ids and summaries for all perps markets. Market summaries include
        information about the market's price, open interest, funding rate,
        and skew::

            markets_by_name = {
                'ETH': {
                    'market_id': 100,
                    'market_name': 'ETH',
                    'skew': -15,
                    'size': 100,
                    'max_open_interest': 10000,
                    'current_funding_rate': 0.000182,
                    'current_funding_velocity': 0.00002765,
                    'index_price': 1852.59,
                    ...
                }
                'BTC': {
                    ...
                }
            }

        :return: Market summaries keyed by `market_id` and `market_name`.
        :rtype: (dict, dict)
        """
        market_ids = self.market_proxy.functions.getActiveMarketIds().call()

        # get market configurations
        market_digests = multicall_erc7412(
            self.snx, self.market_proxy, "getMarketDigest", market_ids
        )
        market_config = call_erc7412(
            self.snx,
            self.market_proxy,
            "getMarketConfiguration",
            (),
        )
        market_configs = multicall_erc7412(
            self.snx, self.market_proxy, "getMarketConfigurationById", market_ids
        )

        self.market_meta = {
            market_id: {
                "market_id": market_id,
                "market_name": market_digests[ind][1].decode("utf-8").strip("\x00"),
                "symbol": market_digests[ind][1].decode("utf-8").strip("\x00")[:-4],
                "feed_id": encode_hex(market_configs[ind][1]),
                "system_config": unpack_bfp_configuration(market_config),
                "market_config": unpack_bfp_configuration_by_id(market_configs[ind]),
            }
            for ind, market_id in enumerate(market_ids)
        }

        # update pyth price feed ids
        self.snx.pyth.update_price_feed_ids(
            {
                self.market_meta[market]["symbol"]: self.market_meta[market]["feed_id"]
                for market in self.market_meta
            }
        )

        # fetch the market summaries
        self.markets_by_id = {
            market_id: {
                "market_id": market_id,
                "market_name": self.market_meta[market_id]["market_name"],
                "feed_id": self.market_meta[market_id]["feed_id"],
                "skew": wei_to_ether(market_digests[ind][2]),
                "size": wei_to_ether(market_digests[ind][3]),
                "oracle_price": wei_to_ether(market_digests[ind][4]),
                "funding_velocity": wei_to_ether(market_digests[ind][5]),
                "funding_rate": wei_to_ether(market_digests[ind][6]),
                "utilization_rate": wei_to_ether(market_digests[ind][7]),
                "remaining_liquidatable_size_capacity": wei_to_ether(
                    market_digests[ind][8]
                ),
                "last_liquidation_time": market_digests[ind][9],
                "total_trader_debt_usd": wei_to_ether(market_digests[ind][10]),
                "total_collateral_value_usd": wei_to_ether(market_digests[ind][11]),
                "debt_correction": wei_to_ether(market_digests[ind][12]),
                "market_config": unpack_bfp_configuration_by_id(market_configs[ind]),
            }
            for ind, market_id in enumerate(market_ids)
        }

        # make markets by market name
        self.markets_by_name = {
            summary["market_name"]: summary for summary in self.markets_by_id.values()
        }
        return self.markets_by_id, self.markets_by_name

    def get_order(
        self, account_id: int = None, market_id: int = None, market_name: str = None
    ):
        """
        Fetches the open order for an account.

        :param int | None account_id: The id of the account. If not provided, the default account is used.
        :return: A dictionary with order information.
        :rtype: dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if not account_id:
            account_id = self.default_account_id

        order = call_erc7412(
            self.snx, self.market_proxy, "getOrderDigest", (account_id, market_id)
        )

        return {
            "market_id": market_id,
            "market_name": market_name,
            "size_delta": wei_to_ether(order[0]),
            "commitment_time": order[1],
            "limit_price": wei_to_ether(order[2]),
            "keeper_fee_buffer_usd": wei_to_ether(order[3]),
            "hooks": order[4],
            "is_stale": order[5],
            "is_ready": order[6],
        }

    def get_margin_info(self, account_id: int = None, market_id: int = None):
        """
        Fetch comprehensive information about an account's margin requirements, balances, and position.

        :param int | None account_id: The id of the account to fetch the margin info for. If not provided, the default account is used.
        :param int | None market_id: The id of the market to fetch the margin info for. Required parameter.
        :return: A dictionary with detailed margin and position information.
        :rtype: dict
        """
        if not account_id:
            account_id = self.default_account_id

        if market_id is None:
            raise ValueError("market_id must be provided")

        account_digest = call_erc7412(
            self.snx, self.market_proxy, "getAccountDigest", (account_id, market_id)
        )

        deposited_collaterals = {
            self.snx.web3.to_checksum_address(collateral[0]): {
                "collateral_address": self.snx.web3.to_checksum_address(collateral[0]),
                "available": wei_to_ether(collateral[1]),
                "oracle_price": wei_to_ether(collateral[2]),
            }
            for collateral in account_digest[0]
        }

        position_digest = account_digest[3]

        return {
            "collateral_balances": deposited_collaterals,
            "collateral_usd": wei_to_ether(account_digest[1]),
            "debt_usd": wei_to_ether(account_digest[2]),
            "position": {
                "account_id": position_digest[0],
                "market_id": position_digest[1],
                "remaining_margin_usd": wei_to_ether(position_digest[2]),
                "health_factor": wei_to_ether(position_digest[3]),
                "notional_value_usd": wei_to_ether(position_digest[4]),
                "pnl": wei_to_ether(position_digest[5]),
                "accrued_funding": wei_to_ether(position_digest[6]),
                "accrued_utilization": wei_to_ether(position_digest[7]),
                "entry_pyth_price": wei_to_ether(position_digest[8]),
                "entry_price": wei_to_ether(position_digest[9]),
                "oracle_price": wei_to_ether(position_digest[10]),
                "size": wei_to_ether(position_digest[11]),
                "initial_margin": wei_to_ether(position_digest[12]),
                "maintenance_margin": wei_to_ether(position_digest[13]),
            },
        }

    def get_open_position(
        self, market_id: int = None, market_name: str = None, account_id: int = None
    ):
        """
        Fetch the position for a specified account and market. The result includes detailed
        information about the position, including unrealized PnL, funding, size, and various margins.

        :param int | None market_id: The id of the market to fetch the position for.
        :param str | None market_name: The name of the market to fetch the position for.
        :param int | None account_id: The id of the account to fetch the position for. If not provided, the default account is used.
        :return: A dictionary with comprehensive position information.
        :rtype: dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if not account_id:
            account_id = self.default_account_id

        position = call_erc7412(
            self.snx, self.market_proxy, "getPositionDigest", (account_id, market_id)
        )

        return {
            "account_id": position[0],
            "market_id": position[1],
            "remaining_margin_usd": wei_to_ether(position[2]),
            "health_factor": wei_to_ether(position[3]),
            "notional_value_usd": wei_to_ether(position[4]),
            "pnl": wei_to_ether(position[5]),
            "accrued_funding": wei_to_ether(position[6]),
            "accrued_utilization": wei_to_ether(position[7]),
            "entry_pyth_price": wei_to_ether(position[8]),
            "entry_price": wei_to_ether(position[9]),
            "oracle_price": wei_to_ether(position[10]),
            "position_size": wei_to_ether(position[11]),
            "initial_margin": wei_to_ether(position[12]),
            "maintenance_margin": wei_to_ether(position[13]),
            "market_name": market_name,
        }

    def get_quote(
        self,
        size: float,
        market_id: int = None,
        market_name: str = None,
        account_id: int = None,
        keeper_fee_buffer_usd: float = 0,
    ):
        """
        Get a quote for the size of an order in a specified market. The quote includes
        the fill price of the order after price impact, estimated fees, and other relevant information.

        :param float size: The size of the order to quote (positive for long, negative for short).
        :param int | None market_id: The id of the market to quote the order for.
        :param str | None market_name: The name of the market to quote the order for.
        :param int | None account_id: The id of the account to quote the order for. If not provided, the default account is used.
        :param float keeper_fee_buffer_usd: Additional keeper fee buffer in USD.
        :return: A dictionary with the quote information.
        :rtype: dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if not account_id:
            account_id = self.default_account_id

        # Convert size to wei
        size_wei = ether_to_wei(size)

        # Get the current oracle price
        oracle_price = call_erc7412(
            self.snx, self.market_proxy, "getOraclePrice", (market_id,)
        )

        # Get the fill price
        fill_price = call_erc7412(
            self.snx, self.market_proxy, "getFillPrice", (market_id, size_wei)
        )

        # Get the order fees
        keeper_fee_buffer_usd_wei = ether_to_wei(keeper_fee_buffer_usd)
        order_fee, keeper_fee = call_erc7412(
            self.snx,
            self.market_proxy,
            "getOrderFees",
            (market_id, size_wei, keeper_fee_buffer_usd_wei),
        )

        # Calculate the price impact
        price_impact = (fill_price - oracle_price) / oracle_price

        return {
            "market_id": market_id,
            "market_name": market_name,
            "size": size,
            "oracle_price": wei_to_ether(oracle_price),
            "fill_price": wei_to_ether(fill_price),
            "price_impact": float(price_impact),
            "order_fee": wei_to_ether(order_fee),
            "keeper_fee": wei_to_ether(keeper_fee),
            "total_fee": wei_to_ether(order_fee + keeper_fee),
            "notional_value": abs(size) * wei_to_ether(fill_price),
            "side": "long" if size > 0 else "short",
        }

    def get_can_liquidate(
        self, account_id: int = None, market_id: int = None, market_name: str = None
    ):
        """
        Check if an ``account_id`` is eligible for liquidation on a specified market

        :param int | None account_id: The id of the account to check. If not provided, the default account is used.
        :return: A boolean indicating if the account is eligible for liquidation.
        :rtype: bool
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if not account_id:
            account_id = self.default_account_id

        # call the liquidation functions
        is_position_liquidatable = call_erc7412(
            self.snx,
            self.market_proxy,
            "isPositionLiquidatable",
            (account_id, market_id),
        )
        is_margin_liquidatable = call_erc7412(
            self.snx,
            self.market_proxy,
            "isMarginLiquidatable",
            (account_id, market_id),
        )

        return {
            "is_position_liquidatable": is_position_liquidatable,
            "is_margin_liquidatable": is_margin_liquidatable,
        }

    def modify_collateral(
        self,
        amount: float,
        collateral_address: str,
        market_id: int = None,
        market_name: str = None,
        account_id: int = None,
        submit: bool = False,
    ):
        """
        Modify the collateral for a specified account and market. Positive amounts deposit
        collateral, while negative amounts withdraw collateral.

        :param float amount: The amount of collateral to modify. Positive values deposit, negative values withdraw.
        :param str collateral_address: The address of the collateral token to modify.
        :param int | None market_id: The id of the market to modify collateral for.
        :param str | None market_name: The name of the market to modify collateral for.
        :param int | None account_id: The id of the account to modify collateral for. If not provided, the default account is used.
        :param bool submit: If True, submit the transaction to the blockchain. If False, return the transaction parameters.
        :return: If submit is True, returns the transaction hash. Otherwise, returns the transaction parameters.
        :rtype: str | dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if not account_id:
            account_id = self.default_account_id

        # Convert amount to wei
        amount_wei = ether_to_wei(amount)

        # Prepare the transaction
        tx_params = write_erc7412(
            self.snx,
            self.market_proxy,
            "modifyCollateral",
            [account_id, market_id, collateral_address, amount_wei],
        )

        if submit:
            try:
                tx_hash = self.snx.execute_transaction(tx_params)
                self.logger.info(
                    f"Modifying collateral for account {account_id} in market {market_name}"
                )
                self.logger.info(f"Moving {amount} of collateral {collateral_address}")
                self.logger.info(f"modifyCollateral tx: {tx_hash}")
                return tx_hash
            except Exception as e:
                self.logger.error(f"Failed to modify collateral: {str(e)}")
                raise
        else:
            return tx_params

    def commit_order(
        self,
        size: float,
        market_id: int = None,
        market_name: str = None,
        account_id: int = None,
        limit_price: float = None,
        keeper_fee_buffer_usd: float = 0,
        hooks: list = None,
        submit: bool = False,
    ):
        """
        Commit an order to the specified market.

        :param float size: The size of the order to submit. Positive for long, negative for short.
        :param int | None market_id: The id of the market to submit the order to.
        :param str | None market_name: The name of the market to submit the order to.
        :param int | None account_id: The id of the account to submit the order for. Defaults to default_account_id.
        :param float | None limit_price: The limit price for the order. If not provided, will use the current oracle price.
        :param float keeper_fee_buffer_usd: Additional keeper fee buffer in USD.
        :param list | None hooks: List of settlement hook addresses.
        :param bool submit: If True, submit the transaction to the blockchain. If False, return the transaction parameters.

        :return: If submit is True, returns the transaction hash. Otherwise, returns the transaction parameters.
        :rtype: str | dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if not account_id:
            account_id = self.default_account_id

        # Convert size to wei
        size_wei = ether_to_wei(size)

        # If limit price is not provided, use the current oracle price
        if limit_price is None:
            oracle_price = call_erc7412(
                self.snx, self.market_proxy, "getOraclePrice", (market_id,)
            )
            limit_price = wei_to_ether(oracle_price)

        # Convert limit price to wei
        limit_price_wei = ether_to_wei(limit_price)

        # Convert keeper fee buffer to wei
        keeper_fee_buffer_usd_wei = ether_to_wei(keeper_fee_buffer_usd)

        # Prepare hooks
        if hooks is None:
            hooks = []

        # Prepare the transaction
        tx_params = write_erc7412(
            self.snx,
            self.market_proxy,
            "commitOrder",
            [
                account_id,
                market_id,
                size_wei,
                limit_price_wei,
                keeper_fee_buffer_usd_wei,
                hooks,
                self.snx.tracking_code,
            ],
        )

        if submit:
            try:
                tx_hash = self.snx.execute_transaction(tx_params)
                self.logger.info(
                    f"Committing order for account {account_id} in market {market_name}"
                )
                self.logger.info(f"Order size: {size}, Limit Price: {limit_price}")
                self.logger.info(f"commitOrder tx: {tx_hash}")
                return tx_hash
            except Exception as e:
                self.logger.error(f"Failed to commit order: {str(e)}")
                raise
        else:
            return tx_params

    def settle_order(
        self,
        account_id: int = None,
        market_id: int = None,
        market_name: str = None,
        max_attempts: int = 3,
        attempt_delay: int = 5,
        submit: bool = False,
    ):
        """
        Settle an open order for the specified account and market.

        :param int | None account_id: The id of the account to settle the order for. If not provided, uses the default account.
        :param int | None market_id: The id of the market to settle the order in.
        :param str | None market_name: The name of the market to settle the order in.
        :param int max_attempts: Maximum number of attempts to settle the order.
        :param int attempt_delay: Delay in seconds between settlement attempts.
        :param bool submit: If True, submit the transaction to the blockchain. If False, return the transaction parameters.
        :return: If submit is True, returns the transaction hash. Otherwise, returns the transaction parameters.
        :rtype: str | dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if not account_id:
            account_id = self.default_account_id

        # Fetch market configuration to get the Pyth price feed ID
        pyth_price_feed_id = self.snx.perps.markets_by_id[market_id]["feed_id"]
        order = self.get_order(account_id, market_id=market_id)
        self.logger.info(f"Order: {order}")

        min_publish_delay = self.market_meta[market_id]["system_config"][
            "pyth_publish_time_min"
        ]
        max_publish_delay = self.market_meta[market_id]["system_config"][
            "pyth_publish_time_max"
        ]

        commitment_time = order["commitment_time"]
        publish_time = commitment_time + min_publish_delay

        wait_amount = publish_time - time.time()
        if wait_amount > 0:
            self.logger.info(f"Waiting {wait_amount} seconds to settle order")
            time.sleep(wait_amount)

        for attempt in range(max_attempts):
            try:
                # Fetch the latest Pyth price update data
                pyth_data = self.snx.pyth.get_price_from_ids(
                    [pyth_price_feed_id], publish_time=publish_time
                )
                price_update_data = pyth_data["price_update_data"][0]

                # Prepare the transaction
                tx_params = write_erc7412(
                    self.snx,
                    self.market_proxy,
                    "settleOrder",
                    [account_id, market_id, price_update_data],
                    tx_params={"value": 1},
                )

                if submit:
                    tx_hash = self.snx.execute_transaction(tx_params)
                    self.logger.info(
                        f"Settling order for account {account_id} in market {market_name}"
                    )
                    self.logger.info(f"settleOrder tx: {tx_hash}")

                    # Wait for transaction to be mined
                    receipt = self.snx.wait(tx_hash)
                    if receipt["status"] == 1:
                        self.logger.info("Order settled successfully")
                        return tx_hash
                    else:
                        raise Exception("Transaction failed")
                else:
                    return tx_params

            except Exception as e:
                self.logger.warning(
                    f"Settlement attempt {attempt + 1} failed: {str(e)}"
                )
                if attempt < max_attempts - 1:
                    self.logger.info(f"Retrying in {attempt_delay} seconds...")
                    time.sleep(attempt_delay)
                else:
                    self.logger.error("Max attempts reached. Settlement failed.")
                    raise

        raise Exception("Failed to settle order after maximum attempts")

    def cancel_stale_order(
        self,
        account_id: int = None,
        market_id: int = None,
        market_name: str = None,
        submit: bool = False,
    ):
        """
        Cancels and order for the specified account and market.

        :param int | None account_id: The id of the account to cancel the order for. If not provided, uses the default account.
        :param int | None market_id: The id of the market to cancel the order in.
        :param str | None market_name: The name of the market to cancel the order in.
        :param bool submit: If True, submit the transaction to the blockchain. If False, return the transaction parameters.
        :return: If submit is True, returns the transaction hash. Otherwise, returns the transaction parameters.
        :rtype: str | dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if account_id is None:
            account_id = self.default_account_id

        # Prepare the transaction
        tx_params = write_erc7412(
            self.snx,
            self.market_proxy,
            "cancelStaleOrder",
            [
                account_id,
                market_id,
            ],
        )

        if submit:
            try:
                tx_hash = self.snx.execute_transaction(tx_params)
                self.logger.info(
                    f"Cancelling stale order for account {account_id} in market {market_name}"
                )
                self.logger.info(f"cancelStaleOrder tx: {tx_hash}")
                return tx_hash
            except Exception as e:
                self.logger.error(f"Failed to cancel order: {str(e)}")
                raise
        else:
            return tx_params

    def pay_debt(
        self,
        amount: int = None,
        account_id: int = None,
        market_id: int = None,
        market_name: str = None,
        submit: bool = False,
    ):
        """
        Pay the debt of a perps account. If no amount is provided, the full debt
        of the account is repaid. Make sure to approve the proxy to transfer sUSD before
        calling this function.

        :param int | None amount: The amount of debt to repay. If not provided, the full debt is repaid.
        :param int | None account_id: The id of the account to repay the debt for. If not provided, the default account is used.
        :param bool submit: If ``True``, submit the transaction to the blockchain.
        :return: If ``submit``, returns the trasaction hash. Otherwise, returns the transaction.
        :rtype: str | dict
        """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if account_id is None:
            account_id = self.default_account_id

        if amount is None:
            account_digest = call_erc7412(
                self.snx,
                self.market_proxy,
                "getAccountDigest",
                (account_id, market_id),
            )
            amount = account_digest[2]
        else:
            amount = ether_to_wei(amount)

        tx_params = write_erc7412(
            self.snx,
            self.market_proxy,
            "payDebt",
            [account_id, market_id, amount],
        )
        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(f"Repaying debt of {amount} for account {account_id}")
            self.logger.info(f"payDebt tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def liquidate(
        self,
        account_id: int = None,
        market_id: int = None,
        market_name: str = None,
        margin_only: bool = False,
        submit: bool = False,
    ):
        """ """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if account_id is None:
            account_id = self.default_account_id

        fn_name = "liquidatePosition" if not margin_only else "liquidateMarginOnly"
        tx_params = write_erc7412(
            self.snx,
            self.market_proxy,
            fn_name,
            [account_id, market_id],
        )
        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(
                f"Liquidating account {account_id} in market {market_name}"
            )

            self.logger.info(f"{fn_name} tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params

    def flag(
        self,
        account_id: int = None,
        market_id: int = None,
        market_name: str = None,
        submit: bool = False,
    ):
        """ """
        market_id, market_name = self._resolve_market(market_id, market_name)
        if account_id is None:
            account_id = self.default_account_id

        tx_params = write_erc7412(
            self.snx,
            self.market_proxy,
            "flagPosition",
            [account_id, market_id],
        )
        if submit:
            tx_hash = self.snx.execute_transaction(tx_params)
            self.logger.info(f"Flagging account {account_id} in market {market_name}")

            self.logger.info(f"flagPosition tx: {tx_hash}")
            return tx_hash
        else:
            return tx_params
