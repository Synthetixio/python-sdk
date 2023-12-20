import requests
import base64
from web3.exceptions import ContractCustomError
from web3._utils.abi import get_abi_output_types
from eth_abi import decode, encode
from eth_utils import encode_hex, decode_hex

# constants
ORACLE_DATA_REQUIRED = "0xcf2cabdf"


def decode_result(contract, function_name, result):
    # get the function abi
    func_abi = contract.get_function_by_name(function_name).abi
    output_types = get_abi_output_types(func_abi)

    # decode the result
    return decode(output_types, result)


# ERC-7412 support
def decode_erc7412_error(snx, error):
    """Decodes an OracleDataRequired error"""
    # remove the signature and decode the error data
    error_data = decode_hex(f"0x{error[10:]}")

    # decode the result
    output_types = ["address", "bytes"]
    address, data = decode(output_types, error_data)
    address = snx.web3.to_checksum_address(address)

    # decode the bytes data into the arguments for the oracle
    output_type_update_type = ["uint8"]
    update_type = decode(output_type_update_type, data)[0]

    try:
        output_types_oracle = ["uint8", "uint64", "bytes32[]"]
        update_type, staleness_tolerance, raw_feed_ids = decode(
            output_types_oracle, data
        )

        feed_ids = [encode_hex(raw_feed_id) for raw_feed_id in raw_feed_ids]
        return address, feed_ids, (update_type, staleness_tolerance, raw_feed_ids)
    except:
        pass

    try:
        output_types_oracle = ["uint8", "uint64", "bytes32"]
        update_type, publish_time, raw_feed_id = decode(output_types_oracle, data)

        feed_ids = [encode_hex(raw_feed_id)]
        raw_feed_ids = [raw_feed_id]
        return address, feed_ids, (update_type, publish_time, raw_feed_ids)
    except:
        pass

    raise Exception("Error data can not be decoded")


def make_fulfillment_request(snx, address, price_update_data, args):
    erc_contract = snx.web3.eth.contract(
        address=address, abi=snx.contracts["PythERC7412Wrapper"]["abi"]
    )

    update_type, publish_time_or_staleness, feed_ids = args
    encoded_args = encode(
        ["uint8", "uint64", "bytes32[]", "bytes[]"],
        [update_type, publish_time_or_staleness, feed_ids, price_update_data],
    )

    # assume 1 wei per price update
    value = len(price_update_data) * 1

    update_tx = erc_contract.functions.fulfillOracleQuery(
        encoded_args
    ).build_transaction({"value": value, "gas": None})
    return update_tx["to"], update_tx["data"], update_tx["value"]


def handle_erc7412_error(snx, error, calls):
    if type(error) is ContractCustomError and error.data.startswith(
        ORACLE_DATA_REQUIRED
    ):
        # decode error data
        address, feed_ids, args = decode_erc7412_error(snx, error.data)
        update_type = args[0]

        if update_type == 1:
            # fetch the data from pyth for those feed ids
            price_update_data = snx.pyth.get_feeds_data(feed_ids)

            # create a new request
            to, data, value = make_fulfillment_request(
                snx, address, price_update_data, args
            )
        elif update_type == 2:
            # fetch the data from pyth for those feed ids
            price_update_data, _, _ = snx.pyth.get_benchmark_data(feed_ids[0], args[1])

            # create a new request
            to, data, value = make_fulfillment_request(
                snx, address, [price_update_data], args
            )
        else:
            snx.logger.error(f"Unknown update type: {update_type}")
            raise error

        calls = [(to, True, value, data)] + calls
        return calls
    else:
        snx.logger.error(f"Error is not related to oracle data: {error}")
        raise error


def write_erc7412(snx, contract, function_name, args, tx_params={}, calls=[]):
    # prepare the initial call
    this_call = [
        (
            contract.address,
            True,
            0 if "value" not in tx_params else tx_params["value"],
            bytes.fromhex(contract.encodeABI(fn_name=function_name, args=args)[2:]),
        )
    ]
    calls = calls + this_call

    while True:
        try:
            # unpack calls into the multicallThrough inputs
            total_value = sum([i[2] for i in calls])

            # create the transaction and do a static call
            tx_params = snx._get_tx_params(value=total_value)
            tx_params = snx.multicall.functions.aggregate3Value(
                calls
            ).build_transaction(tx_params)

            # buffer the gas limit
            tx_params["gas"] = int(tx_params["gas"] * 1.15)

            # if simulation passes, return the transaction
            snx.logger.info(f"Simulated tx successfully: {tx_params}")
            return tx_params
        except Exception as e:
            # check if the error is related to oracle data
            snx.logger.info(f"Simulation failed, decoding the error {e}")

            # handle the error by appending calls
            calls = handle_erc7412_error(snx, e, calls)


def call_erc7412(snx, contract, function_name, args, calls=[], block="latest"):
    # fix args
    args = args if isinstance(args, (list, tuple)) else (args,)

    # prepare the initial calls
    this_call = (
        contract.address,
        True,
        0,
        contract.encodeABI(fn_name=function_name, args=args),
    )
    calls = calls + [this_call]

    while True:
        try:
            total_value = sum(i[2] for i in calls)

            # call it
            tx_params = snx._get_tx_params(value=total_value)
            call = snx.multicall.functions.aggregate3Value(calls).call(
                tx_params, block_identifier=block
            )

            # call was successful, decode the result
            decoded_result = decode_result(contract, function_name, call[-1][1])
            return decoded_result if len(decoded_result) > 1 else decoded_result[0]

        except Exception as e:
            # check if the error is related to oracle data
            snx.logger.info(f"Simulation failed, decoding the error {e}")

            # handle the error by appending calls
            calls = handle_erc7412_error(snx, e, calls)


def multicall_erc7412(
    snx, contract, function_name, args_list, calls=[], block="latest"
):
    # check if args is a list of lists or tuples
    # correct the format if it is not
    args_list = [
        args if isinstance(args, (list, tuple)) else (args,) for args in args_list
    ]
    num_prepended_calls = len(calls)

    # prepare the initial calls
    these_calls = [
        (
            contract.address,
            True,
            0,
            contract.encodeABI(fn_name=function_name, args=args),
        )
        for args in args_list
    ]
    calls = calls + these_calls
    num_calls = len(calls) - num_prepended_calls

    while True:
        try:
            total_value = sum(i[2] for i in calls)

            # call it
            call = snx.multicall.functions.aggregate3Value(calls).call(
                {"value": total_value}, block_identifier=block
            )

            # call was successful, decode the result
            calls_to_decode = call[-num_calls:]

            decoded_results = [
                decode_result(contract, function_name, result[1])
                for result in calls_to_decode
            ]
            decoded_results = [
                decoded_result if len(decoded_result) > 1 else decoded_result[0]
                for decoded_result in decoded_results
            ]
            return decoded_results

        except Exception as e:
            # check if the error is related to oracle data
            snx.logger.info(f"Simulation failed, decoding the error {e}")

            # handle the error by appending calls
            calls = handle_erc7412_error(snx, e, calls)
