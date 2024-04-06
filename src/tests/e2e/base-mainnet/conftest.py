import os
import logging
import pytest
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# constants
RPC = os.environ.get("LOCAL_RPC")
ADDRESS = os.environ.get("ADDRESS")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")

# find an address with a lot of usdc
USDC_WHALE = "0x20FE51A9229EEf2cF8Ad9E89d91CAb9312cF3b7A"


# fixtures
@pytest.fixture(scope="module")
def snx(pytestconfig):
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=RPC,
        address=ADDRESS,
        private_key=PRIVATE_KEY,
        network_id=8453,
    )

    # check usdc balance
    usdc_contract = snx.contracts["USDC"]["contract"]
    usdc_balance = usdc_contract.functions.balanceOf(ADDRESS).call()
    usdc_balance = usdc_balance / 10**6

    # get some usdc
    if usdc_balance < 10000:
        transfer_amount = int((10000 - usdc_balance) * 10**6)
        snx.web3.provider.make_request("anvil_impersonateAccount", [USDC_WHALE])

        tx_params = usdc_contract.functions.transfer(
            ADDRESS, transfer_amount
        ).build_transaction(
            {
                "from": USDC_WHALE,
                "nonce": snx.web3.eth.get_transaction_count(USDC_WHALE),
            }
        )

        # Send the transaction directly without signing
        tx_hash = snx.web3.eth.send_transaction(tx_params)
        receipt = snx.wait(tx_hash)
        if receipt["status"] != 1:
            raise Exception("USDC Transfer failed")

        # wrap some USDC
        approve_tx_1 = snx.approve(
            usdc_contract.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx_1)

        wrap_tx = snx.spot.wrap(5000, market_name="sUSDC", submit=True)
        snx.wait(wrap_tx)

        # sell some for sUSD
        approve_tx_2 = snx.spot.approve(
            snx.spot.market_proxy.address, market_name="sUSDC", submit=True
        )
        snx.wait(approve_tx_2)

        susd_tx = snx.spot.atomic_order("sell", 2500, market_name="sUSDC", submit=True)
        snx.wait(susd_tx)

    return snx


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


@pytest.fixture(scope="function")
def new_account_id(pytestconfig, snx, logger):
    logger.info("Creating a new perps account")
    create_tx = snx.perps.create_account(submit=True)
    snx.wait(create_tx)

    account_ids = snx.perps.get_account_ids()
    new_account_id = account_ids[-1]

    yield new_account_id


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
