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
    output_types = [i['type'] for i in func['outputs']]

    # create the inputs
    inputs = [
        (contract.address, True, contract.encodeABI(fn_name=function_name, args=i))
        for i in inputs
    ]

    # call multicall and decode
    mc_result = multicall_contract.functions.aggregate3(inputs).call()
    mc_result = [decode(output_types, x[1]) for x in mc_result if x[0] == True]

    # if there is only one result, return it as a single value
    mc_result = [x[0] for x in mc_result if len(x) == 1]
    return mc_result
