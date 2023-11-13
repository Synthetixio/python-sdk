import os
import logging
import pytest
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# constants
RPC = os.environ.get('PROVIDER_RPC')
ADDRESS = os.environ.get('ADDRESS')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')

# fixtures
@pytest.fixture(scope="module")
def snx(pytestconfig):
    # TODO: add allowance checks
    return Synthetix(
        provider_rpc=RPC,
        address=ADDRESS,
        private_key=PRIVATE_KEY,
        network_id=84531
    )
    
@pytest.fixture(scope="module")
def account_id(pytestconfig, snx, logger):
    # check if an account exists
    account_ids = snx.perps.get_account_ids()
    
    # TODO: add account setup
    if len(account_ids) > 0:
        logger.info(f'Account already exists: {account_ids[-1]}')
        account_id = account_ids[-1]
    else:
        logger.info('Creating a new perps account')
        
        create_tx = snx.perps.create_account(submit=True)
        snx.wait(create_tx)
        
        account_ids = snx.perps.get_account_ids()
        assert len(account_ids) > 0
        account_id = account_ids[0]

    yield account_id

    # TODO: check open positions and close them
    
    # withdraw all collateral
    collateral_balances = snx.perps.get_collateral_balances(account_id)
    for market_name, balance in collateral_balances.items():
        if balance > 0:
            withdraw_tx = snx.perps.modify_collateral(-balance, market_name=market_name, account_id=account_id, submit=True)
            snx.wait(withdraw_tx)
    
