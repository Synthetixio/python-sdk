import os
from web3.exceptions import ContractCustomError
from eth_abi import decode, encode
from eth_utils import encode_hex, decode_hex
from synthetix import Synthetix
from synthetix.utils.multicall import (
    handle_erc7412_error,
    SELECTOR_ERRORS,
    SELECTOR_ORACLE_DATA_REQUIRED,
    SELECTOR_ORACLE_DATA_REQUIRED_WITH_FEE,
)

# constants
ODR_ERROR_TYPES = ["address", "bytes"]
ODR_FEE_ERROR_TYPES = ["address", "bytes", "uint256"]

ODR_BYTES_TYPES = {
    1: ["uint8", "uint64", "bytes32[]"],
    2: ["uint8", "uint64", "bytes32"],
}


# encode some errors
def encode_odr_error(snx, inputs, with_fee=False):
    "Utility to help encode errors to test"
    types = ODR_FEE_ERROR_TYPES if with_fee else ODR_ERROR_TYPES
    fee = [1] if with_fee else []
    address = snx.contracts["pyth_erc7412_wrapper"]["PythERC7412Wrapper"]["address"]

    # get the update type
    update_type = inputs[0]
    bytes_types = ODR_BYTES_TYPES[update_type]

    # encode bytes
    error_bytes = encode(bytes_types, inputs)

    # encode the error
    error = encode(types, [address, error_bytes] + fee)
    return error


# tests


def test_update_type_1_with_staleness(snx):
    # Test update_type 1 with staleness 3600
    feed_id = snx.pyth.price_feed_ids["ETH"]
    error = encode_odr_error(snx, (1, 3600, [decode_hex(feed_id)]))
    error_hex = SELECTOR_ORACLE_DATA_REQUIRED + error.hex()

    custom_error = ContractCustomError(message="Test error", data=error_hex)
    calls = handle_erc7412_error(snx, custom_error, [])

    assert len(calls) == 1, "Expected 1 call for update_type 1"
    assert calls[0][1] == True, "Expected call to be marked as static"
    assert calls[0][2] > 0, "Expected non-zero value for the call"


def test_update_type_2_with_recent_publish_time(snx):
    # Test update_type 2 with a publish_time in the last 60 seconds
    feed_id = snx.pyth.price_feed_ids["BTC"]
    current_time = snx.web3.eth.get_block("latest").timestamp
    recent_publish_time = current_time - 30  # 30 seconds ago

    error = encode_odr_error(snx, (2, recent_publish_time, decode_hex(feed_id)))
    error_hex = SELECTOR_ORACLE_DATA_REQUIRED + error.hex()

    custom_error = ContractCustomError(message="Test error", data=error_hex)
    calls = handle_erc7412_error(snx, custom_error, [])

    assert len(calls) == 1, "Expected 1 call for update_type 2"
    assert calls[0][1] == True, "Expected call to be marked as static"
    assert calls[0][2] > 0, "Expected non-zero value for the call"


def test_oracle_data_required_with_fee(snx):
    # Test OracleDataRequired error with fee
    feed_id = snx.pyth.price_feed_ids["ETH"]
    error = encode_odr_error(snx, (1, 3600, [decode_hex(feed_id)]), with_fee=True)
    error_hex = SELECTOR_ORACLE_DATA_REQUIRED_WITH_FEE + error.hex()

    custom_error = ContractCustomError(message="Test error", data=error_hex)
    calls = handle_erc7412_error(snx, custom_error, [])

    assert len(calls) == 1, "Expected 1 call for OracleDataRequired with fee"
    assert calls[0][1] == True, "Expected call to be marked as static"
    assert calls[0][2] > 0, "Expected non-zero value for the call"


def test_errors_with_multiple_sub_errors(snx):
    # Test Errors error which includes multiple individual errors
    feed_id_1 = snx.pyth.price_feed_ids["ETH"]
    feed_id_2 = snx.pyth.price_feed_ids["BTC"]

    error_1 = encode_odr_error(snx, (1, 3600, [decode_hex(feed_id_1)]))
    error_1_hex = SELECTOR_ORACLE_DATA_REQUIRED + error_1.hex()

    error_2 = encode_odr_error(
        snx, (2, snx.web3.eth.get_block("latest").timestamp - 30, decode_hex(feed_id_2))
    )
    error_2_hex = SELECTOR_ORACLE_DATA_REQUIRED + error_2.hex()

    # Encode multiple errors
    errors_data = encode(
        ["bytes[]"], [(decode_hex(error_1_hex), decode_hex(error_2_hex))]
    )

    errors_hex = SELECTOR_ERRORS + errors_data.hex()

    custom_error = ContractCustomError(message="Test error", data=errors_hex)
    calls = handle_erc7412_error(snx, custom_error, [])

    assert len(calls) == 2, "Expected 2 calls for Errors with 2 sub-errors"
    for call in calls:
        assert call[1] == True, "Expected all calls to be marked as static"
        assert call[2] > 0, "Expected non-zero value for all calls"
