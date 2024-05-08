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


def test_spot_wrap_usdc(snx, contracts, steal_usdc):
    """The instance can wrap USDC for sUSDC"""
    usdc = contracts["USDC"]

    # make sure we have some USDC
    balance_wei = usdc.functions.balanceOf(snx.address).call()
    balance = format_wei(balance_wei, 6)

    synth_balance = snx.spot.get_balance(market_name="sUSDC")

    assert balance > 0

    # check the allowance
    allowance = snx.allowance(usdc.address, snx.spot.market_proxy.address)

    if allowance < TEST_AMOUNT:
        # approve
        approve_tx = snx.approve(
            usdc.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # wrap
    wrap_tx = snx.spot.wrap(TEST_AMOUNT, market_name="sUSDC", submit=True)
    snx.wait(wrap_tx)

    # get new balances
    new_balance_wei = usdc.functions.balanceOf(snx.address).call()
    new_balance = format_wei(new_balance_wei, 6)

    new_synth_balance = snx.spot.get_balance(market_name="sUSDC")

    assert new_balance == balance - TEST_AMOUNT
    assert new_synth_balance == synth_balance + TEST_AMOUNT


def test_spot_unwrap_usdc(snx, contracts, steal_usdc, logger):
    """The instance can unwrap sUSDC for USDC"""
    usdc = contracts["USDC"]
    susdc = snx.spot.markets_by_name["sUSDC"]["contract"]

    # check balances
    balance_wei = usdc.functions.balanceOf(snx.address).call()
    balance = format_wei(balance_wei, 6)

    synth_balance = snx.spot.get_balance(market_name="sUSDC")

    assert synth_balance >= TEST_AMOUNT

    # check the allowance
    allowance = snx.allowance(susdc.address, snx.spot.market_proxy.address)

    if allowance < TEST_AMOUNT:
        # approve
        approve_tx = snx.approve(
            susdc.address, snx.spot.market_proxy.address, submit=True
        )
        snx.logger.info(approve_tx)
        snx.wait(approve_tx)

    # unwrap
    unwrap_tx = snx.spot.wrap(-TEST_AMOUNT, market_name="sUSDC", submit=True)
    snx.wait(unwrap_tx)

    # get new balances
    new_balance_wei = usdc.functions.balanceOf(snx.address).call()
    new_balance = format_wei(new_balance_wei, 6)

    new_synth_balance = snx.spot.get_balance(market_name="sUSDC")

    assert new_balance == balance + TEST_AMOUNT
    assert new_synth_balance == synth_balance - TEST_AMOUNT


def test_spot_wrap_dai(snx, contracts, mint_dai):
    """The instance can wrap DAI for sDAI"""
    dai = contracts["DAI"]

    # make sure we have some USDC
    balance_wei = dai.functions.balanceOf(snx.address).call()
    balance = format_wei(balance_wei, 6)

    synth_balance = snx.spot.get_balance(market_name="sDAI")

    assert balance > 0

    # check the allowance
    allowance = snx.allowance(dai.address, snx.spot.market_proxy.address)

    if allowance < TEST_AMOUNT:
        # approve
        approve_tx = snx.approve(
            dai.address, snx.spot.market_proxy.address, submit=True
        )
        snx.wait(approve_tx)

    # wrap
    wrap_tx = snx.spot.wrap(TEST_AMOUNT, market_name="sDAI", submit=True)
    snx.wait(wrap_tx)

    # get new balances
    new_balance_wei = dai.functions.balanceOf(snx.address).call()
    new_balance = format_wei(new_balance_wei, 6)

    new_synth_balance = snx.spot.get_balance(market_name="sDAI")

    assert new_balance == balance - TEST_AMOUNT
    assert new_synth_balance == synth_balance + TEST_AMOUNT


def test_spot_unwrap_dai(snx, contracts, mint_dai, logger):
    """The instance can unwrap sDAI for DAI"""
    dai = contracts["DAI"]
    sdai = snx.spot.markets_by_name["sDAI"]["contract"]

    # check balances
    balance_wei = dai.functions.balanceOf(snx.address).call()
    balance = format_wei(balance_wei, 6)

    synth_balance = snx.spot.get_balance(market_name="sDAI")

    assert synth_balance >= TEST_AMOUNT

    # check the allowance
    allowance = snx.allowance(sdai.address, snx.spot.market_proxy.address)

    if allowance < TEST_AMOUNT:
        # approve
        approve_tx = snx.approve(
            sdai.address, snx.spot.market_proxy.address, submit=True
        )
        snx.logger.info(approve_tx)
        snx.wait(approve_tx)

    # wrap
    wrap_tx = snx.spot.wrap(-TEST_AMOUNT, market_name="sDAI", submit=True)
    snx.wait(wrap_tx)

    # get new balances
    new_balance_wei = dai.functions.balanceOf(snx.address).call()
    new_balance = format_wei(new_balance_wei, 6)

    new_synth_balance = snx.spot.get_balance(market_name="sDAI")

    assert new_balance == balance + TEST_AMOUNT
    assert new_synth_balance == synth_balance - TEST_AMOUNT


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
