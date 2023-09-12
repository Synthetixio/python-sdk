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


def multicall_function(snx, contract, function_name, inputs):
    """Multicall a specified function for a list of inputs"""
    # create a multicall instance
    multicall_contract = snx.web3.eth.contract(
        address=snx.contracts['Multicall']['address'],
        abi=snx.contracts['Multicall']['abi']
    )

    # create the inputs
    inputs = [
        (contract.address, True, contract.encodeABI(fn_name=function_name, args=i))
        for i in inputs
    ]

    # call multicall and decode
    mc_result = multicall_contract.functions.aggregate3(inputs).call()
    mc_result = [decode_result(contract, function_name, x[1]) for x in mc_result if x[0] == True]

    # if there is only one result, return it as a single value
    mc_result = [x[0] if len(x) == 1 else x for x in mc_result]
    return mc_result

# ERC-7412 support
def fetch_pyth_data(snx, error_to_decode):
    """Decodes an OracleDataRequired error and fetches the data from pyth"""
    error_data = decode_hex(f'0x{error_to_decode[10:]}')

    output_types = ['address', 'bytes']

    # decode the result
    address, data = decode(output_types, error_data)
    address = snx.web3.to_checksum_address(address)

    # decode those
    output_types_oracle = ['uint8', 'uint64', 'bytes32[]']
    tag, staleness_tolerance, raw_feed_ids = decode(output_types_oracle, data)
    feed_ids = [encode_hex(raw_feed_id) for raw_feed_id in raw_feed_ids]

    # fetch data from pyth
    url = f"{snx.pyth._price_service_endpoint}/api/latest_vaas"
    params = {
        'ids[]': feed_ids
    }

    response = requests.get(url, params, timeout=10)
    return address, base64.b64decode(response.json()[0]), (tag, staleness_tolerance, raw_feed_ids)


def make_fulfillment_request(snx, address, price_update_data, decoded_args):
    erc_contract = snx.web3.eth.contract(
        address=address,
        abi=snx.contracts['ERC7412']['abi']
    )
    flag, staleness_tolerance, feed_ids = decoded_args
    
    encoded_args = encode(['uint8', 'uint64', 'bytes32[]', 'bytes[]'], [
        flag,
        staleness_tolerance,
        feed_ids,
        [price_update_data]
    ])

    update_tx = erc_contract.functions.fulfillOracleQuery(
        encoded_args
    ).build_transaction({'value': 1, 'gas': None})
    return update_tx['to'], update_tx['data'], update_tx['value']

def write_erc7412(snx, contract, function_name, args, tx_params={}):
    # prepare the initial call
    calls = [(
        contract.address,
        contract.encodeABI(
            fn_name=function_name,
            args=args
        ),
        0 if 'value' not in tx_params else tx_params['value']
    )]

    while True:
        try:
            # unpack calls into the multicallThrough inputs
            addresses, data, values = zip(*calls)
            total_value = sum(values)

            # create the transaction and do a static call
            tx_params = snx._get_tx_params(value=total_value)
            tx_params['to'] = contract.address
            tx_params['data'] = contract.encodeABI(fn_name='multicallThrough', args=[
                addresses, data, values])
            
            print('TX params: ', tx_params)

            estimate = snx.web3.eth.estimate_gas(tx_params)

            # if estimate passes, return the transaction
            return tx_params
        except Exception as e:
            # check if the error is related to oracle data
            if type(e) is ContractCustomError and e.data.startswith(ORACLE_DATA_REQUIRED):
                # decode error data
                address, price_update_data, decoded_args = fetch_pyth_data(snx, e.data)

                # create a new request
                to, data, value = make_fulfillment_request(snx, address, price_update_data, decoded_args)
                calls = calls[:-1] + [(to, data, value)] + calls[-1:]
            else:
                snx.logger.error(f'Error is not related to oracle data: {e}')
                return tx_params


def call_erc7412(snx, contract, function_name, args):
    # get a multicall contract
    multicall = snx.web3.eth.contract(
        address=snx.contracts['Multicall']['address'],
        abi=snx.contracts['Multicall']['abi']
    )

    # fix args
    args = args if isinstance(args, (list, tuple)) else (args,)

    # prepare the initial calls
    calls = [(
        contract.address,
        False,
        0,
        contract.encodeABI(
            fn_name=function_name,
            args=args
        )
    )]
    while True:
        try:
            total_value = sum(i[2] for i in calls)

            # call it
            call = multicall.functions.aggregate3Value(calls).call({'value': total_value})

            # call was successful, decode the result
            decoded_result = decode_result(contract, function_name, call[-1][1])
            return decoded_result if len(decoded_result) > 1 else decoded_result[0]

        except Exception as e:
            if type(e) is ContractCustomError and e.data.startswith(ORACLE_DATA_REQUIRED):
                # decode error data
                address, price_update_data, decoded_args = fetch_pyth_data(snx, e.data)

                # create a new request
                to, data, value = make_fulfillment_request(snx, address, price_update_data, decoded_args)
                calls = calls[:-1] + [(to, False, value, data)] + calls[-1:]
            else:
                print('Error is not related to oracle data')
                print(e)
                return None

def multicall_erc7412(snx, contract, function_name, args_list):
    # get a multicall contract
    multicall = snx.web3.eth.contract(
        address=snx.contracts['Multicall']['address'],
        abi=snx.contracts['Multicall']['abi']
    )
    
    # check if args is a list of lists or tuples
    # correct the format if it is not
    args_list = [
        args if isinstance(args, (list, tuple)) else (args,)
        for args in args_list
    ]

    # prepare the initial calls
    calls = [(
        contract.address,
        False,
        0,
        contract.encodeABI(
            fn_name=function_name,
            args=args
        )
    ) for args in args_list]
    
    num_calls = len(calls)
    while True:
        try:
            total_value = sum(i[2] for i in calls)

            # call it
            call = multicall.functions.aggregate3Value(calls).call({'value': total_value})

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
                address, price_update_data, decoded_args = fetch_pyth_data(snx, e.data)

                # create a new request
                to, data, value = make_fulfillment_request(snx, address, price_update_data, decoded_args)
                calls = [(to, False, value, data)] + calls
            else:
                print('Error is not related to oracle data')
                print(e)
                return None
