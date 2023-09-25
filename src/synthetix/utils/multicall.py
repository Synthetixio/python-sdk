import requests
import base64
from web3.exceptions import ContractCustomError
from web3._utils.abi import get_abi_output_types
from eth_abi import decode, encode
from eth_utils import encode_hex, decode_hex

# constants
ORACLE_DATA_REQUIRED = '0xcf2cabdf'

def decode_result(contract, function_name, result):
    # get the function abi
    func_abi = contract.get_function_by_name(function_name).abi
    output_types = get_abi_output_types(func_abi)
    
    # decode the result
    return decode(output_types, result)

# ERC-7412 support
def decode_erc7412_error(snx, error):
    """Decodes an OracleDataRequired error """
    # remove the signature and decode the error data
    error_data = decode_hex(f'0x{error[10:]}')

    # decode the result
    output_types = ['address', 'bytes']
    address, data = decode(output_types, error_data)
    address = snx.web3.to_checksum_address(address)

    # decode the bytes data into the arguments for the oracle
    output_types_oracle = ['uint8', 'uint64', 'bytes32[]']
    tag, staleness_tolerance, raw_feed_ids = decode(output_types_oracle, data)
    feed_ids = [encode_hex(raw_feed_id) for raw_feed_id in raw_feed_ids]
    return address, feed_ids, (tag, staleness_tolerance, raw_feed_ids)


def make_fulfillment_request(snx, address, price_update_data, args):
    erc_contract = snx.web3.eth.contract(
        address=address,
        abi=snx.contracts['ERC7412']['abi']
    )
    
    encoded_args = encode(['uint8', 'uint64', 'bytes32[]', 'bytes[]'], [
        *args,
        price_update_data
    ])

    update_tx = erc_contract.functions.fulfillOracleQuery(
        encoded_args
    ).build_transaction({'value': 1, 'gas': None})
    return update_tx['to'], update_tx['data'], update_tx['value']

def write_erc7412(snx, contract, function_name, args, tx_params={}, calls = []):
    # prepare the initial call
    this_call = [(
        contract.address,
        False,
        0 if 'value' not in tx_params else tx_params['value'],
        bytes.fromhex(contract.encodeABI(
            fn_name=function_name,
            args=args
        )[2:])
    )]
    calls = calls + this_call

    while True:
        try:
            # unpack calls into the multicallThrough inputs
            total_value = sum([i[2] for i in calls])

            # create the transaction and do a static call
            tx_params = snx._get_tx_params(value=total_value)
            tx_params = snx.multicall.functions.aggregate3Value(calls).build_transaction(tx_params)
            
            # buffer the gas limit
            tx_params['gas'] = int(tx_params['gas'] * 1.15)

            # if simulation passes, return the transaction
            snx.logger.info(f'Simulated tx successfully: {tx_params}')
            return tx_params
        except Exception as e:
            # check if the error is related to oracle data
            if type(e) is ContractCustomError and e.data.startswith(ORACLE_DATA_REQUIRED):
                # decode error data
                address, feed_ids, args = decode_erc7412_error(snx, e.data)
                
                # fetch the data from pyth for those feed ids
                price_update_data = snx.pyth.get_feeds_data(feed_ids)

                # create a new request
                to, data, value = make_fulfillment_request(snx, address, price_update_data, args)
                calls = calls[:-1] + [(to, False, value, data)] + calls[-1:]
            else:
                snx.logger.error(f'Error is not related to oracle data: {e}')
                raise e

def call_erc7412(snx, contract, function_name, args, calls = [], block='latest'):
    # fix args
    args = args if isinstance(args, (list, tuple)) else (args,)

    # prepare the initial calls
    this_call = (
        contract.address,
        False,
        0,
        contract.encodeABI(
            fn_name=function_name,
            args=args
        )
    )
    calls = calls + [this_call]

    while True:
        try:
            total_value = sum(i[2] for i in calls)

            # call it
            tx_params = snx._get_tx_params(value=total_value)
            call = snx.multicall.functions.aggregate3Value(calls).call(tx_params, block_identifier=block)

            # call was successful, decode the result
            decoded_result = decode_result(contract, function_name, call[-1][1])
            return decoded_result if len(decoded_result) > 1 else decoded_result[0]

        except Exception as e:
            if type(e) is ContractCustomError and e.data.startswith(ORACLE_DATA_REQUIRED):
                # decode error data
                address, feed_ids, args = decode_erc7412_error(snx, e.data)
                
                # fetch the data from pyth for those feed ids
                price_update_data = snx.pyth.get_feeds_data(feed_ids)

                # create a new request
                to, data, value = make_fulfillment_request(snx, address, price_update_data, args)
                calls = calls[:-1] + [(to, False, value, data)] + calls[-1:]
            else:
                snx.logger.error(f'Error is not related to oracle data: {e}')
                raise e

def multicall_erc7412(snx, contract, function_name, args_list, calls = [], block='latest'):
    # check if args is a list of lists or tuples
    # correct the format if it is not
    args_list = [
        args if isinstance(args, (list, tuple)) else (args,)
        for args in args_list
    ]
    num_prepended_calls = len(calls)

    # prepare the initial calls
    these_calls = [(
        contract.address,
        False,
        0,
        contract.encodeABI(
            fn_name=function_name,
            args=args
        )
    ) for args in args_list]
    calls = calls + these_calls
    num_calls = len(calls) - num_prepended_calls

    while True:
        try:
            total_value = sum(i[2] for i in calls)

            # call it
            call = snx.multicall.functions.aggregate3Value(calls).call({'value': total_value}, block_identifier=block)

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
            if type(e) is ContractCustomError and e.data.startswith(ORACLE_DATA_REQUIRED):
                # decode error data
                address, feed_ids, args = decode_erc7412_error(snx, e.data)
                
                # fetch the data from pyth for those feed ids
                price_update_data = snx.pyth.get_feeds_data(feed_ids)

                # create a new request
                to, data, value = make_fulfillment_request(snx, address, price_update_data, args)
                calls = [(to, False, value, data)] + calls
            else:
                snx.logger.error(f'Error is not related to oracle data: {e}')
                raise e
