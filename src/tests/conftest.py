import os
import logging
import pytest
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()

# constants
RPC = os.environ.get('BASE_TESTNET_RPC')
ADDRESS = os.environ.get('ADDRESS')

# fixtures
@pytest.fixture(scope="module")
def snx(pytestconfig):
    return Synthetix(
        provider_rpc=RPC,
        address=ADDRESS,
        network_id=84531
    )

@pytest.fixture(scope="module")
def logger(pytestconfig):
    logg = logging.getLogger(__name__)
    if not logg.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
        logg.addHandler(handler)
    return logg
