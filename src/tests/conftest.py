import os
import logging
import pytest
from synthetix import Synthetix
from dotenv import load_dotenv

load_dotenv()


# Add a command-line option to pytest to accept network_id
def pytest_addoption(parser):
    parser.addoption(
        "--network_id", action="store", help="Network ID for testing", default=84531
    )


@pytest.fixture(scope="module")
def network_id(pytestconfig):
    return pytestconfig.getoption("network_id")


# fixtures
@pytest.fixture(scope="module")
def snx(pytestconfig):
    network_id = pytestconfig.getoption("network_id")
    rpc_key = f"NETWORK_{network_id}_RPC"
    rpc = os.environ.get(rpc_key)
    address = os.environ.get("ADDRESS")
    if not rpc or not address:
        raise ValueError(f"RPC not specified for network ID {network_id}")

    snx = Synthetix(provider_rpc=rpc, address=address, network_id=network_id)
    snx.logger.info(f"Using network ID {network_id}")
    return snx


@pytest.fixture(scope="module")
def logger(pytestconfig):
    logg = logging.getLogger(__name__)
    if not logg.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        )
        logg.addHandler(handler)
    return logg
