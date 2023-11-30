from pytest import raises
from synthetix import Synthetix
from synthetix.utils import wei_to_ether
from dotenv import load_dotenv

load_dotenv()

# tests
TEST_AMOUNT = 100


def test_spot_module(snx, logger):
    """The instance has a spot module"""
    assert snx.spot is not None
    assert snx.spot.market_proxy is not None

def test_spot_markets(snx, logger):
    """The instance has an sUSDC market"""
    assert 'sUSDC' in snx.spot.markets_by_name
    assert snx.spot.markets_by_name['sUSDC']['contract'] is not None

def test_spot_wrap(snx, logger):
    """The instance can wrap USDC for sUSDC"""
    # use the mintable token on testnet
    usdc = snx.contracts['MintableToken']['contract']
    
    # make sure we have some USDC
    balance_wei = usdc.functions.balanceOf(snx.address).call()
    balance = wei_to_ether(balance_wei)
    
    synth_balance = snx.spot.get_balance(market_name='sUSDC')
    
    assert balance > 0
    
    # check the allowance
    allowance = snx.allowance(usdc.address, snx.spot.market_proxy.address)
    
    if allowance < TEST_AMOUNT:
        # approve
        approve_tx = snx.approve(usdc.address, snx.spot.market_proxy.address)
        snx.wait(approve_tx)
    
    # wrap
    wrap_tx = snx.spot.wrap(TEST_AMOUNT, market_name='sUSDC', submit=True)
    snx.wait(wrap_tx)
    
    # get new balances
    new_balance_wei = usdc.functions.balanceOf(snx.address).call()
    new_balance = wei_to_ether(new_balance_wei)
    
    new_synth_balance = snx.spot.get_balance(market_name='sUSDC')
    
    assert new_balance == balance - TEST_AMOUNT
    assert new_synth_balance == synth_balance + TEST_AMOUNT

def test_spot_unwrap(snx, logger):
    """The instance can unwrap sUSDC for USDC"""
    # use the mintable token on testnet
    usdc = snx.contracts['MintableToken']['contract']
    susdc = snx.spot.markets_by_name['sUSDC']['contract']
    
    # check balances
    balance_wei = usdc.functions.balanceOf(snx.address).call()
    balance = wei_to_ether(balance_wei)
    
    synth_balance = snx.spot.get_balance(market_name='sUSDC')
    
    assert synth_balance >= TEST_AMOUNT

    # check the allowance
    allowance = snx.allowance(
        susdc.address,
        snx.spot.market_proxy.address
    )
    
    if allowance < TEST_AMOUNT:
        # approve
        approve_tx = snx.approve(susdc.address, snx.spot.market_proxy.address)
        snx.wait(approve_tx)
    
    # wrap
    wrap_tx = snx.spot.wrap(-TEST_AMOUNT, market_name='sUSDC', submit=True)
    snx.wait(wrap_tx)
    
    # get new balances
    new_balance_wei = usdc.functions.balanceOf(snx.address).call()
    new_balance = wei_to_ether(new_balance_wei)
    
    new_synth_balance = snx.spot.get_balance(market_name='sUSDC')
    
    assert new_balance == balance + TEST_AMOUNT
    assert new_synth_balance == synth_balance - TEST_AMOUNT
