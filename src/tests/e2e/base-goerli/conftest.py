import os
import logging
import pytest
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# constants
RPC = os.environ.get("NETWORK_84531_RPC")
ADDRESS = os.environ.get("ADDRESS")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")


# fixtures
@pytest.fixture(scope="module")
def snx(pytestconfig):
    # TODO: add allowance checks
    return Synthetix(
        provider_rpc=RPC,
        address=ADDRESS,
        private_key=PRIVATE_KEY,
        network_id=84531,
    )


@pytest.fixture(scope="module")
def account_id(pytestconfig, snx, logger):
    # check if an account exists
    account_ids = snx.perps.get_account_ids()

    final_account_id = None
    for account_id in account_ids:
        margin_info = snx.perps.get_margin_info(account_id)
        positions = snx.perps.get_open_positions(account_id=account_id)

        if margin_info["total_collateral_value"] == 0 and len(positions) == 0:
            logger.info(f"Account {account_id} is empty")
            final_account_id = account_id
            break
        else:
            logger.info(f"Account {account_id} has margin")

    if final_account_id is None:
        logger.info("Creating a new perps account")

        create_tx = snx.perps.create_account(submit=True)
        snx.wait(create_tx)

        account_ids = snx.perps.get_account_ids()
        final_account_id = account_ids[-1]

    yield final_account_id

    close_positions_and_withdraw(snx, final_account_id)


def close_positions_and_withdraw(snx, account_id):
    # close positions
    positions = snx.perps.get_open_positions(account_id=account_id)

    for market_name in positions:
        size = positions[market_name]["position_size"]

        commit_tx = snx.perps.commit_order(
            -size, market_name=market_name, account_id=account_id, submit=True
        )
        snx.wait(commit_tx)

        # wait for the order settlement
        snx.perps.settle_order(account_id=account_id, submit=True)

        # check the result
        position = snx.perps.get_open_position(
            market_name=market_name, account_id=account_id
        )
        assert position["position_size"] == 0

    # withdraw all collateral
    collateral_balances = snx.perps.get_collateral_balances(account_id)
    for market_name, balance in collateral_balances.items():
        if balance > 0:
            withdraw_tx = snx.perps.modify_collateral(
                -balance, market_name=market_name, account_id=account_id, submit=True
            )
            snx.wait(withdraw_tx)
