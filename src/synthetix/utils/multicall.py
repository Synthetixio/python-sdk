from eth_typing import HexStr
import requests
import base64
from web3.exceptions import ContractCustomError
from web3._utils.abi import get_abi_output_types
from eth_abi import decode, encode
from eth_utils import encode_hex, decode_hex


# constants
SELECTOR_ORACLE_DATA_REQUIRED = "0xcf2cabdf"
SELECTOR_ORACLE_DATA_REQUIRED_WITH_FEE = "0x0e7186fb"
SELECTOR_ERRORS = "0x0b42fd17"


def decode_result(contract, function_name, result):
    # get the function abi
    func_abi = contract.get_function_by_name(function_name).abi
    output_types = get_abi_output_types(func_abi)

    # decode the result
    return decode(output_types, result)


# ERC-7412 support
def decode_erc7412_errors_error(error):
    """Decodes an Errors error"""
    error_data = decode_hex(f"0x{error[10:]}")

    errors = decode(["bytes[]"], error_data)[0]
    errors = [ContractCustomError(data=encode_hex(e)) for e in errors]
    errors.reverse()

    return errors


def decode_erc7412_oracle_data_required_error(snx, error):
    """Decodes an OracleDataRequired error"""
    # remove the signature and decode the error data
    error_data = decode_hex(f"0x{error[10:]}")

    # decode the result
    # could be one of two types with different args
    output_types = ["address", "bytes", "uint256"]
    try:
        address, data, fee = decode(output_types, error_data)
    except:
        address, data = decode(output_types[:2], error_data)
        fee = 0

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
        return address, feed_ids, fee, (update_type, staleness_tolerance, raw_feed_ids)
    except:
        pass

    try:
        output_types_oracle = ["uint8", "uint64", "bytes32"]
        update_type, publish_time, raw_feed_id = decode(output_types_oracle, data)

        feed_ids = [encode_hex(raw_feed_id)]
        raw_feed_ids = [raw_feed_id]
        return address, feed_ids, fee, (update_type, publish_time, raw_feed_ids)
    except:
        pass

    raise Exception("Error data can not be decoded")


def make_pyth_fulfillment_request(
    snx,
    address,
    update_type,
    feed_ids,
    price_update_data,
    publish_time_or_staleness,
    fee,
):
    # log all of the inputs
    erc_contract = snx.web3.eth.contract(
        address=address,
        abi=snx.contracts["pyth_erc7412_wrapper"]["PythERC7412Wrapper"]["abi"],
    )

    # update_type, publish_time_or_staleness, feed_ids = args
    feed_ids = [decode_hex(f) for f in feed_ids]
    encoded_args = encode(
        ["uint8", "uint64", "bytes32[]", "bytes[]"],
        [update_type, publish_time_or_staleness, feed_ids, price_update_data],
    )

    # assume 1 wei per price update
    value = fee if fee > 0 else len(feed_ids) * 1

    update_tx = erc_contract.functions.fulfillOracleQuery(
        encoded_args
    ).build_transaction({"value": value, "gas": None})
    return update_tx["to"], update_tx["data"], update_tx["value"]


class PythVaaRequest:
    feed_ids: list[HexStr] = []
    publish_time = 0
    fee = 0


class ERC7412Requests:
    pyth_address = ""
    pyth_latest: list[HexStr] = []
    pyth_latest_fee = 0
    pyth_vaa: list[PythVaaRequest] = []


def aggregate_erc7412_price_requests(snx, error, requests=None):
    "Figures out all the prices that have been requested by an ERC7412 error and puts them all in aggregated requests"
    if not requests:
        requests = ERC7412Requests()
    if type(error) is ContractCustomError and error.data.startswith(SELECTOR_ERRORS):
        errors = decode_erc7412_errors_error(error.data)

        # TODO: execute in parallel
        for sub_error in errors:
            requests = aggregate_erc7412_price_requests(snx, sub_error, requests)

        return requests
    if type(error) is ContractCustomError and (
        error.data.startswith(SELECTOR_ORACLE_DATA_REQUIRED)
        or error.data.startswith(SELECTOR_ORACLE_DATA_REQUIRED_WITH_FEE)
    ):
        # decode error data
        update_type = None
        address = ""
        feed_ids = []
        fee = 0
        args = []
        try:
            address, feed_ids, fee, args = decode_erc7412_oracle_data_required_error(
                snx, error.data
            )
            update_type = args[0]
        except:
            pass

        if update_type:
            requests.pyth_address = address
            if update_type == 1:
                # fetch the data from pyth for those feed ids
                requests.pyth_latest = requests.pyth_latest + feed_ids
                requests.pyth_latest_fee = requests.pyth_latest_fee + fee
            elif update_type == 2:
                # fetch the data from pyth for those feed ids
                vaa_request = PythVaaRequest()
                vaa_request.feed_ids = feed_ids
                vaa_request.publish_time = args[1]
                vaa_request.fee = fee
                requests.pyth_vaa = requests.pyth_vaa + [vaa_request]
            else:
                snx.logger.error(f"Unknown update type: {update_type}")
                raise error
    else:
        try:
            is_nonce_error = (
                "message" in error.args[0]
                and "nonce" in error.args[0]["message"].lower()
            )
        except:
            is_nonce_error = False

        if is_nonce_error:
            snx.logger.debug(f"Error is related to nonce, resetting nonce")
            snx.nonce = snx.web3.eth.get_transaction_count(snx.address)
            return requests
        else:
            snx.logger.debug(f"Error is not related to oracle data")
            raise error

    return requests


def handle_erc7412_error(snx, error):
    "When receiving a ERC7412 error, will return an updated list of calls with the required price updates"
    requests = aggregate_erc7412_price_requests(snx, error)
    calls = []

    if len(requests.pyth_latest) > 0:
        # fetch the data from pyth for those feed ids
        if not snx.is_fork:
            pyth_data = snx.pyth.get_price_from_ids(requests.pyth_latest)
            price_update_data = pyth_data["price_update_data"]
        else:
            # if it's a fork, get the price for the latest block
            # this avoids providing "future" prices to the contract on a fork
            block = snx.web3.eth.get_block("latest")

            # set a manual 60 second staleness
            publish_time = block.timestamp - 60
            pyth_data = snx.pyth.get_price_from_ids(
                requests.pyth_latest, publish_time=publish_time
            )
            price_update_data = pyth_data["price_update_data"]

        # create a new request
        # TODO: the actual number should go here for staleness
        to, data, value = make_pyth_fulfillment_request(
            snx,
            requests.pyth_address,
            1,
            requests.pyth_latest,
            price_update_data,
            3600,
            requests.pyth_latest_fee,
        )

        calls.append((to, True, value, data))

    if len(requests.pyth_vaa) > 0:
        for r in requests.pyth_vaa:
            # fetch the data from pyth for those feed ids
            pyth_data = snx.pyth.get_price_from_ids(
                r.feed_ids, publish_time=r.publish_time
            )
            price_update_data = pyth_data["price_update_data"]

            # create a new request
            to, data, value = make_pyth_fulfillment_request(
                snx,
                requests.pyth_address,
                2,
                r.feed_ids,
                price_update_data,
                r.publish_time,
                r.fee,
            )

            calls.append((to, True, value, data))

    # note: more calls (ex. new oracle providers) can be added here in the future

    return calls


def write_erc7412(snx, contract, function_name, args, tx_params={}, calls=[]):
    # prepare the initial call
    this_call = [
        (
            contract.address,
            True,
            0 if "value" not in tx_params else tx_params["value"],
            contract.encodeABI(fn_name=function_name, args=args),
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
            snx.logger.debug(f"Simulated tx successfully: {tx_params}")
            return tx_params
        except Exception as e:
            # check if the error is related to oracle data
            snx.logger.debug(f"Simulation failed, decoding the error {e}")

            # handle the error by appending calls
            calls = handle_erc7412_error(snx, e) + calls


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
            snx.logger.debug(f"Simulation failed, decoding the error {e}")

            # handle the error by appending calls
            calls = handle_erc7412_error(snx, e) + calls


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
            snx.logger.debug(f"Simulation failed, decoding the error {e}")

            # handle the error by appending calls
            calls = handle_erc7412_error(snx, e) + calls
