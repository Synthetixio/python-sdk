import os
import json
import glob
import zlib
import requests
from web3 import Web3


def load_contracts(snx):
    """loads the contracts for a synthetix instance and overrides with cannon if set"""
    # first load local contracts
    contracts = load_local_contracts(snx)

    # if true, load cannon contracts and override local contracts
    if snx.cannon_config is not None:
        # if the keys contain "package", "version", and "preset", then load from cannon
        if snx.cannon_config.keys() >= {"package", "version", "preset"}:
            package, version, preset = (
                snx.cannon_config["package"],
                snx.cannon_config["version"],
                snx.cannon_config["preset"],
            )
            snx.logger.info(
                f"Loading cannon contracts for {package}:{version}@{preset}"
            )
            deployment_hash = get_deployment_hash(snx)
            cannon_contracts = fetch_deploy_from_ipfs(snx, deployment_hash)
            contracts.update(cannon_contracts)
        elif snx.cannon_config.keys() >= {"ipfs_hash"}:
            deployment_hash = snx.cannon_config["ipfs_hash"]
            snx.logger.info(
                f"Loading cannon contracts at ipfs hash ipfs://{deployment_hash}"
            )
            cannon_contracts = fetch_deploy_from_ipfs(snx, deployment_hash)
            contracts.update(cannon_contracts)
    return contracts


def load_local_contracts(snx):
    """loads the contracts for a synthetix instance"""
    deployment_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "deployments", f"{snx.network_id}"
    )
    contracts = load_json_files_from_directory(snx, deployment_dir)
    return contracts


def load_json_files_from_directory(snx, directory):
    """load json files from a given directory"""
    json_files = glob.glob(os.path.join(directory, "*.json"))
    contracts = {
        os.path.splitext(os.path.basename(file))[0]: json.load(open(file))
        for file in json_files
    }

    # add a web3 contract object
    contracts = {
        k: {
            "address": v["address"],
            "abi": v["abi"],
            "contract": snx.web3.eth.contract(address=v["address"], abi=v["abi"]),
        }
        for k, v in contracts.items()
    }
    return contracts


def get_deployment_hash(snx):
    provider_rpc = snx.mainnet_rpc
    w3 = (
        Web3(Web3.HTTPProvider(provider_rpc))
        if provider_rpc.startswith("http")
        else Web3(Web3.WebsocketProvider(provider_rpc))
    )

    deployment_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "deployments", "1"
    )
    cannon_file = os.path.join(deployment_dir, "CannonRegistry.json")
    with open(cannon_file, "r") as file:
        cannon_contract_def = json.load(file)

    contract = w3.eth.contract(
        address=cannon_contract_def["address"], abi=cannon_contract_def["abi"]
    )

    chain_id = snx.network_id
    package = encode_string(snx.cannon_config["package"])
    version = encode_string(snx.cannon_config["version"])
    preset = encode_string(str(chain_id) + "-" + snx.cannon_config["preset"])

    ipfs_loc = contract.functions.getPackageUrl(package, version, preset).call()
    ipfs_hash = ipfs_loc.split("/")[-1]
    return ipfs_hash


def encode_string(string, length=66, pad_char="0"):
    """encode a string to a fixed length for contract interaction"""
    return Web3.to_hex(text=string).ljust(length, pad_char)


def fetch_deploy_from_ipfs(snx, ipfs_hash):
    url = f"{snx.ipfs_gateway}/{ipfs_hash}"
    response = requests.get(url)
    data = zlib.decompress(response.content)
    data = json.loads(data)

    deployment = parse_contracts(snx, data)
    return deployment


def parse_contracts(snx, deploy_data):
    contracts = dict()
    recursive_search(deploy_data, contracts)
    return {
        k: {
            "address": v["address"],
            "abi": v["abi"],
            "contract": snx.web3.eth.contract(address=v["address"], abi=v["abi"]),
        }
        for k, v in contracts.items()
    }


def recursive_search(deploy_data, contracts):
    """recursively search through deployment data to extract contracts"""
    if isinstance(deploy_data, dict):
        for key, value in deploy_data.items():
            if key == "contracts" and value:
                for contract_name, artifacts in value.items():
                    contracts[contract_name] = artifacts
            if isinstance(value, (dict, list)):
                recursive_search(value, contracts)
    elif isinstance(deploy_data, list):
        for item in deploy_data:
            recursive_search(item, contracts)
