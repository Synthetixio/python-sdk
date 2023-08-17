import os
import json
import glob

def load_contracts(network_id):
    """Loads the contracts for the given network id"""
    # get all filenames from directory `./deployments/[network_id]`
    deployment_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deployments', f'{network_id}')
    deployment_files = glob.glob(os.path.join(deployment_dir, '*.json'))

    contracts = {
        os.path.splitext(os.path.basename(contract))[0]: json.load(open(contract))
        for contract in deployment_files
    }
    return contracts
