import pytest
from synthetix.utils import ether_to_wei, wei_to_ether, format_wei
from dotenv import load_dotenv

load_dotenv()

# constants
TEST_AMOUNT = 100

# tests


def test_spot_module(snx, logger):
    """The instance has a spot module"""
    assert snx.spot is not None
    assert snx.spot.market_proxy is not None


def test_spot_markets(snx, logger):
    """The instance has spot markets"""
    snx.logger.info(f"Markets: {snx.spot.markets_by_name}")
    assert snx.spot.markets_by_name is not None
    assert len(snx.spot.markets_by_name) == len(snx.spot.markets_by_id)
    assert "sUSD" in snx.spot.markets_by_name
    assert "sUSDC" in snx.spot.markets_by_name
    assert "sDAI" in snx.spot.markets_by_name


@pytest.mark.parametrize(
    "token_name, test_amount, decimals",
    [
        ("USDC", TEST_AMOUNT, 6),
        ("DAI", TEST_AMOUNT, 18),
    ],
)
def test_spot_wrapper(
    snx, contracts, steal_usdc, mint_dai, token_name, test_amount, decimals
):
    """The instance can wrap and unwrap an asset"""
    token = contracts[token_name]
    market_id = snx.spot.markets_by_name[f"s{token_name}"]["market_id"]
    wrapped_token = snx.spot.markets_by_id[market_id]["contract"]

    # make sure we have some USDC
    starting_balance_wei = token.functions.balanceOf(snx.address).call()
    starting_balance = format_wei(starting_balance_wei, decimals)

    starting_synth_balance = snx.spot.get_balance(market_id=market_id)

    assert starting_balance > test_amount

    ## wrap
    # check the allowance
    allowance = snx.allowance(token.address, snx.spot.market_proxy.address)

    if allowance < test_amount:
        # approve
        approve_tx = snx.approve(
            token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    wrap_tx = snx.spot.wrap(test_amount, market_id=market_id, submit=True)
    snx.wait(wrap_tx)

    # get new balances
    wrapped_balance_wei = token.functions.balanceOf(snx.address).call()
    wrapped_balance = format_wei(wrapped_balance_wei, decimals)

    wrapped_synth_balance = snx.spot.get_balance(market_id=market_id)

    assert wrapped_balance == starting_balance - test_amount
    assert wrapped_synth_balance == starting_synth_balance + test_amount

    ## unwrap
    # check the allowance
    wrapped_allowance = snx.allowance(
        wrapped_token.address, snx.spot.market_proxy.address
    )

    if wrapped_allowance < test_amount:
        # approve
        approve_tx = snx.approve(
            wrapped_token.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    unwrap_tx = snx.spot.wrap(-test_amount, market_id=market_id, submit=True)
    snx.wait(unwrap_tx)

    # get new balances
    unwrapped_balance_wei = token.functions.balanceOf(snx.address).call()
    unwrapped_balance = format_wei(unwrapped_balance_wei, decimals)

    unwrapped_synth_balance = snx.spot.get_balance(market_id=market_id)

    assert unwrapped_balance == wrapped_balance + test_amount
    assert unwrapped_synth_balance == wrapped_synth_balance - test_amount


def test_spot_atomic_sell_usdc(snx, contracts, steal_usdc, logger):
    """The instance can wrap USDC for sUSDC and sell for sUSD"""
    # using USDC
    usdc = contracts["USDC"]
    susdc = snx.spot.markets_by_name["sUSDC"]["contract"]

    # make sure we have some USDC
    usdc_balance_wei = usdc.functions.balanceOf(snx.address).call()
    usdc_balance = format_wei(usdc_balance_wei, 6)

    susdc_balance = snx.spot.get_balance(market_name="sUSDC")
    susd_balance = snx.spot.get_balance(market_name="sUSD")
    assert usdc_balance >= TEST_AMOUNT

    # check the allowances
    usdc_allowance = snx.allowance(usdc.address, snx.spot.market_proxy.address)
    susdc_allowance = snx.allowance(susdc.address, snx.spot.market_proxy.address)

    if usdc_allowance < TEST_AMOUNT:
        # approve USDC
        approve_tx = snx.approve(
            usdc.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)
    if susdc_allowance < TEST_AMOUNT:
        # approve sUSDC
        approve_tx = snx.approve(
            susdc.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # wrap
    wrap_tx = snx.spot.wrap(TEST_AMOUNT, market_name="sUSDC", submit=True)
    snx.wait(wrap_tx)

    # sell for sUSD
    sell_tx = snx.spot.atomic_order(
        "sell", TEST_AMOUNT, market_name="sUSDC", submit=True
    )
    snx.wait(sell_tx)

    # get new balances
    new_usdc_balance_wei = usdc.functions.balanceOf(snx.address).call()
    new_usdc_balance = format_wei(new_usdc_balance_wei, 6)

    new_susdc_balance = snx.spot.get_balance(market_name="sUSDC")
    new_susd_balance = snx.spot.get_balance(market_name="sUSD")

    assert new_susd_balance == susd_balance + TEST_AMOUNT
    assert new_usdc_balance == usdc_balance - TEST_AMOUNT
    assert new_susdc_balance == susdc_balance


def test_spot_atomic_buy_usdc(snx, contracts, steal_usdc, logger):
    """The instance can buy sUSDC for sUSD and unwarp for USDC"""
    usdc = contracts["USDC"]
    susd = snx.spot.markets_by_name["sUSD"]["contract"]

    usdc_balance_wei = usdc.functions.balanceOf(snx.address).call()
    usdc_balance = format_wei(usdc_balance_wei, 6)

    susd_balance = snx.spot.get_balance(market_name="sUSD")
    susdc_balance = snx.spot.get_balance(market_name="sUSDC")
    assert susd_balance >= TEST_AMOUNT

    # check the allowances
    susd_allowance = snx.allowance(susd.address, snx.spot.market_proxy.address)
    if susd_allowance < TEST_AMOUNT:
        # approve sUSDC
        approve_tx = snx.approve(
            susd.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # buy sUSDC
    buy_tx = snx.spot.atomic_order("buy", TEST_AMOUNT, market_name="sUSDC", submit=True)
    snx.wait(buy_tx)

    # unwrap
    unwrap_tx = snx.spot.wrap(-TEST_AMOUNT, market_name="sUSDC", submit=True)
    snx.wait(unwrap_tx)

    # get new balances
    new_susdc_balance = snx.spot.get_balance(market_name="sUSDC")
    new_susd_balance = snx.spot.get_balance(market_name="sUSD")

    new_usdc_balance_wei = usdc.functions.balanceOf(snx.address).call()
    new_usdc_balance = format_wei(new_usdc_balance_wei, 6)

    assert new_susd_balance == susd_balance - TEST_AMOUNT
    assert new_susdc_balance == susdc_balance
    assert new_usdc_balance == usdc_balance + TEST_AMOUNT


def test_spot_atomic_sell_dai(snx, contracts, mint_dai, logger):
    """The instance can wrap DAI for sDAI and sell for sUSD"""
    # using DAI
    dai = contracts["DAI"]
    sdai = snx.spot.markets_by_name["sDAI"]["contract"]

    # make sure we have some DAI
    dai_balance_wei = dai.functions.balanceOf(snx.address).call()
    dai_balance = format_wei(dai_balance_wei, 6)

    sdai_balance = snx.spot.get_balance(market_name="sDAI")
    susd_balance = snx.spot.get_balance(market_name="sUSD")
    assert dai_balance >= TEST_AMOUNT

    # check the allowances
    dai_allowance = snx.allowance(dai.address, snx.spot.market_proxy.address)
    sdai_allowance = snx.allowance(sdai.address, snx.spot.market_proxy.address)

    if dai_allowance < TEST_AMOUNT:
        # approve DAI
        approve_tx = snx.approve(
            dai.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)
    if sdai_allowance < TEST_AMOUNT:
        # approve sDAI
        approve_tx = snx.approve(
            sdai.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # wrap
    wrap_tx = snx.spot.wrap(TEST_AMOUNT, market_name="sDAI", submit=True)
    snx.wait(wrap_tx)

    # sell for sUSD
    sell_tx = snx.spot.atomic_order(
        "sell", TEST_AMOUNT, market_name="sDAI", submit=True
    )
    snx.wait(sell_tx)

    # get new balances
    new_dai_balance_wei = dai.functions.balanceOf(snx.address).call()
    new_dai_balance = format_wei(new_dai_balance_wei, 6)

    new_sdai_balance = snx.spot.get_balance(market_name="sDAI")
    new_susd_balance = snx.spot.get_balance(market_name="sUSD")

    assert new_susd_balance == susd_balance + TEST_AMOUNT
    assert new_dai_balance == dai_balance - TEST_AMOUNT
    assert new_sdai_balance == sdai_balance


def test_spot_atomic_buy_dai(snx, contracts, mint_dai, logger):
    """The instance can buy sDAI for sUSD and unwarp for DAI"""
    dai = contracts["DAI"]
    susd = snx.spot.markets_by_name["sUSD"]["contract"]

    dai_balance_wei = dai.functions.balanceOf(snx.address).call()
    dai_balance = format_wei(dai_balance_wei, 6)

    susd_balance = snx.spot.get_balance(market_name="sUSD")
    sdai_balance = snx.spot.get_balance(market_name="sDAI")
    assert susd_balance >= TEST_AMOUNT

    # check the allowances
    susd_allowance = snx.allowance(susd.address, snx.spot.market_proxy.address)
    if susd_allowance < TEST_AMOUNT:
        # approve sDAI
        approve_tx = snx.approve(
            susd.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # buy sDAI
    buy_tx = snx.spot.atomic_order("buy", TEST_AMOUNT, market_name="sDAI", submit=True)
    snx.wait(buy_tx)

    # unwrap
    unwrap_tx = snx.spot.wrap(-TEST_AMOUNT, market_name="sDAI", submit=True)
    snx.wait(unwrap_tx)

    # get new balances
    new_sdai_balance = snx.spot.get_balance(market_name="sDAI")
    new_susd_balance = snx.spot.get_balance(market_name="sUSD")

    new_dai_balance_wei = dai.functions.balanceOf(snx.address).call()
    new_dai_balance = format_wei(new_dai_balance_wei, 6)

    assert new_susd_balance == susd_balance - TEST_AMOUNT
    assert new_sdai_balance == sdai_balance
    assert new_dai_balance == dai_balance + TEST_AMOUNT
