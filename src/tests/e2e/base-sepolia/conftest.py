import os
import pytest
from synthetix import Synthetix
from synthetix.utils import wei_to_ether, format_ether
from dotenv import load_dotenv

load_dotenv()

# constants
RPC = os.environ.get("NETWORK_84532_RPC")
ADDRESS = os.environ.get("ADDRESS")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")

# find an address with a lot of usdc
USDC_WHALE = "0xD34EA7278e6BD48DefE656bbE263aEf11101469c"


# fixtures
@pytest.fixture(scope="module")
def snx(pytestconfig):
    # set up the snx instance
    snx = Synthetix(
        provider_rpc=RPC,
        address=ADDRESS,
        private_key=PRIVATE_KEY,
        network_id=84532,
    )

    # check balances
    usdc_contract = snx.contracts["MintableToken"]["contract"]
    usdc_balance = usdc_contract.functions.balanceOf(ADDRESS).call()
    usdc_balance = format_ether(usdc_balance, 6)

    susdc_contract = snx.spot._get_synth_contract(market_name="sUSDC")
    susdc_balance = susdc_contract.functions.balanceOf(ADDRESS).call()
    susdc_balance = wei_to_ether(susdc_balance)

    susd_contract = snx.spot._get_synth_contract(market_name="sUSD")
    susd_balance = susd_contract.functions.balanceOf(ADDRESS).call()
    susd_balance = wei_to_ether(susd_balance)

    assert usdc_balance > 10000
    return snx


@pytest.fixture(scope="module")
def account_id(pytestconfig, snx):
    # check if an account exists
    account_ids = snx.perps.get_account_ids()

    final_account_id = None
    for account_id in account_ids:
        margin_info = snx.perps.get_margin_info(account_id)
        positions = snx.perps.get_open_positions(account_id=account_id)

        if margin_info["total_collateral_value"] <= 0.0001 and len(positions) == 0:
            snx.logger.info(f"Account {account_id} is empty")
            final_account_id = account_id
            break
        else:
            snx.logger.info(f"Account {account_id} has margin")

    if final_account_id is None:
        snx.logger.info("Creating a new perps account")

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
