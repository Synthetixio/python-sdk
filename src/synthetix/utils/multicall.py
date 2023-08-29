from eth_abi import decode

def multicall_function(snx, contract, function_name, inputs):
    """Multicall a specified function for a list of inputs"""
    # create a multicall instance
    multicall_contract = snx.web3.eth.contract(
        address=snx.contracts['Multicall']['address'],
        abi=snx.contracts['Multicall']['abi']
    )

    # get the function abi
    func = contract.get_function_by_name(function_name).abi
    raw_output_types = [
        i['type'] if i['type'] != 'tuple' else [j['type'] for j in i['components']]
        for i in func['outputs']
    ]

    # flatten any list output types
    output_types = []
    for i in raw_output_types:
        if isinstance(i, list):
            output_types.extend(i)
        else:
            output_types.append(i)

    # create the inputs
    inputs = [
        (contract.address, True, contract.encodeABI(fn_name=function_name, args=i))
        for i in inputs
    ]

    # call multicall and decode
    mc_result = multicall_contract.functions.aggregate3(inputs).call()
    mc_result = [decode(output_types, x[1]) for x in mc_result if x[0] == True]

    # if there is only one result, return it as a single value
    mc_result = [x[0] if len(x) == 1 else x for x in mc_result]
    return mc_result