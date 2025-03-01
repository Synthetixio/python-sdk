from synthetix import Synthetix
from icecream import ic
from decimal import Decimal
from loguru import logger
from config import CHECK_INTERVAL, USDC_SYNTH_ADDRESS, RPC_URL
import os
import psycopg2
from datetime import datetime
import time

from web3 import Web3

import argparse


class SynthetixMonitor:
    def __init__(self, env="prod"):
        # 🔌 Database Configuration
        hosts = {
            "dev": "localhost",
            "staging": "staging-db",
            "prod": os.getenv("POSTGRES_HOST", "prod-database"),
        }
        self.db_params = {
            "dbname": os.getenv("POSTGRES_DB", "crypto"),
            "user": os.getenv("POSTGRES_USER", "crypto"),
            "password": os.getenv("POSTGRES_PASSWORD", "crypto"),
            "host": hosts.get(env, "localhost"),
            "port": os.getenv("POSTGRES_PORT", "5432"),
        }
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))

        if not self.w3.is_connected():
            raise Exception("Failed to connect to Base node")
        logger.info(f"Connected to node: {self.w3.is_connected()}")

        # 📊 Create table if not exists
        self.init_db()

    def init_db(self):
        """Create synthetix_positions table if it doesn't exist"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS synthetix_positions (
            id SERIAL PRIMARY KEY,
            wallet_address VARCHAR(42) NOT NULL,
            token VARCHAR NOT NULL,
            account_id BIGINT  NOT NULL,
            amount DECIMAL NOT NULL,
            reward DECIMAL NOT NULL,
            timestamp TIMESTAMP NOT NULL
        );
        -- Create indexes for better query performance
        CREATE INDEX IF NOT EXISTS idx_wallet ON synthetix_positions(wallet_address);
        CREATE INDEX IF NOT EXISTS idx_token ON synthetix_positions(token);
        CREATE INDEX IF NOT EXISTS idx_timestamp ON synthetix_positions(timestamp);
        """
        try:
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    cur.execute(create_table_sql)
                conn.commit()
            logger.info("✅ Database initialized successfully")
        except Exception as e:
            logger.error(f"❌ Database initialization error: {str(e)}")
            raise

    def save_positions(self, wallet_address: str, positions: list):
        """Save positions to database"""
        if not positions:
            return

        insert_sql = """
        INSERT INTO synthetix_positions 
            (wallet_address, token, amount, reward, account_id,  timestamp)
        VALUES 
            (%s, %s,  %s, %s, %s, %s)
        """
        try:
            timestamp = datetime.now()
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    for pos in positions:
                        cur.execute(
                            insert_sql,
                            (
                                wallet_address,
                                pos["token"],
                                float(Decimal(pos["amount"]) / Decimal(10**8)),
                                float(Decimal(pos["reward"])),
                                pos["account_id"],
                                timestamp,
                            ),
                        )
                conn.commit()
            logger.info(
                f"✅ Saved {len(positions)} positions for wallet {wallet_address}"
            )
        except Exception as e:
            logger.error(f"❌ Database save error: {str(e)}")

    def get_positions(self, wallet_address, prices):
        try:
            # time.sleep(5)
            snx = Synthetix(
                provider_rpc=os.getenv("RPC_URL"),
                address=wallet_address,
                network_id=8453,
                cannon_config={
                    "package": "synthetix-omnibus",
                    "version": "latest",
                    "preset": "andromeda",
                },
            )

            # 🔍 Récupération des IDs de compte
            account_ids = snx.core.get_account_ids(wallet_address)
            ic(account_ids)

            coreProxyContract = snx.contracts["system"]["CoreProxy"]["contract"]
            # ic(coreProxyContract)
            # 🔄 Récupération du pool préféré
            preferred_pool = coreProxyContract.functions.getPreferredPool().call()

            # 💫 Récupération des positions
            formatted_positions = []

            # 💫 Pour chaque compte, on récupère les positions
            for account_id in account_ids:
                try:
                    rewards = self.get_rewards(
                        coreProxyContract=coreProxyContract,
                        accountIds=account_ids,
                        preferredPoolId=preferred_pool,
                        usdc=USDC_SYNTH_ADDRESS,
                        prices=prices,
                    )
                    # ic(rewards)

                    tokens = [
                        USDC_SYNTH_ADDRESS  # USDC
                        # Ajoutez d'autres tokens si nécessaire
                    ]

                    for token in tokens:
                        position = coreProxyContract.functions.getPosition(
                            account_ids[0], preferred_pool, USDC_SYNTH_ADDRESS
                        ).call()

                        # 📊 Si la position n'est pas vide
                        if position and position[1] > 0:  # Vérifie si assets > 0
                            formatted_position = {
                                "account_id": account_id,
                                "token": token,
                                "amount": Decimal(position[1]) / Decimal(10**10),
                                "reward": rewards,
                                "pool_id": preferred_pool,
                            }
                            formatted_positions.append(formatted_position)

                except Exception as e:
                    logger.warning(
                        f"⚠️ Error getting position for account {account_id}: {str(e)}"
                    )
                    continue

            return formatted_positions

        except Exception as e:
            logger.error(f"❌ Error in get_positions: {str(e)}")

            return None

    def get_token_prices(self):
        """🏷️ Get real-time token prices"""
        try:
            snx = Synthetix(
                provider_rpc=os.getenv("RPC_URL"),
                # address=wallet_address,
                network_id=8453,
                cannon_config={
                    "package": "synthetix-omnibus",
                    "version": "latest",
                    "preset": "andromeda",
                },
            )
            # USDC is always 1
            prices = {"USDC": Decimal("1.0")}

            SNX_PRICE_ID = (
                "0x39d020f60982ed892abbcd4a06a276a9f9b7bfbce003204c110b6e488f502da3"
            )
            snx_price_data = snx.pyth.get_price_from_ids(SNX_PRICE_ID)

            # Extract price from the response dictionary
            prices["SNX"] = Decimal(str(snx_price_data["meta"][SNX_PRICE_ID]["price"]))

            # ic(prices)

            # Get WETH price from https://www.pyth.network/developers/price-feed-ids
            ETH_PRICE_ID = "0x9d4294bbcd1174d6f2003ec365831e64cc31d9f6f15a2b85399db8d5000960f6"  # Base chain ETH/USD Oracle
            eth_price_data = snx.pyth.get_price_from_ids(ETH_PRICE_ID)

            prices["WETH"] = Decimal(str(eth_price_data["meta"][ETH_PRICE_ID]["price"]))
            # ic(prices)
            prices["wstETH"] = prices["WETH"]
            # ic(prices)
            logger.info(f"""Current token prices:
                USDC: ${prices["USDC"]}
                SNX: ${float(prices["SNX"])}
                WETH: ${float(prices["WETH"])}
                wstETH: ${float(prices["WETH"])}
            """)
            ic(prices)
            return prices

        except Exception as e:
            logger.error(f"❌ Error getting token prices: {str(e)}")
            return None

    def get_rewards(self, coreProxyContract, accountIds, preferredPoolId, usdc, prices):
        """🎁 Get total rewards in USD"""
        try:
            REWARD_DISTRIBUTORS = {
                "0x7A1b3DB73E5B8c58EDC8A821890005064f2B83Fd": {
                    "token": "USDC",
                    "decimals": 18,
                },
                "0xa7163fE9788BF14CcDac854131CAc2C17d1a1676": {
                    "token": "SNX",
                    "decimals": 18,
                },
                "0x2F64ad511C33a78080b114c5ef51370B31488e65": {
                    "token": "WETH",
                    "decimals": 18,
                },
                "0xE8183A61d64ea44a430bB361467063535B769052": {
                    "token": "wstETH",
                    "decimals": 18,
                },
            }
            rewards_info = coreProxyContract.functions.updateRewards(
                preferredPoolId, usdc, accountIds[0]
            ).call()

            # Get token prices from oracle/API - Example prices (you should get real prices)

            total_usd = Decimal("0")

            for i, (amount, distributor) in enumerate(
                zip(rewards_info[0], rewards_info[1])
            ):
                if amount > 0 and distributor in REWARD_DISTRIBUTORS:
                    reward_info = REWARD_DISTRIBUTORS[distributor]
                    token = reward_info["token"]
                    decimals = reward_info["decimals"]

                    # Convert to token amount
                    token_amount = Decimal(str(amount)) / Decimal(10**decimals)
                    # Convert to USD
                    usd_value = token_amount * prices[token]

                    total_usd += usd_value

                    # ic(f"""Reward converted to USD:
                    #     Token: {token}
                    #     Amount: {float(token_amount)} {token}
                    #     Price: ${float(token_prices[token])}
                    #     USD Value: ${float(usd_value)}
                    # """)

            logger.info(f"Total rewards in USD: ${float(total_usd)}")
            return total_usd

        except Exception as e:
            logger.error(f"❌ Error getting rewards: {str(e)}")
            return Decimal(0)


def main():
    parser = argparse.ArgumentParser(description="Synthetix Monitor")
    parser.add_argument(
        "--env",
        default="prod",
        choices=["dev", "staging", "prod"],
        help="Environment to run in",
    )

    args = parser.parse_args()
    while True:
        try:
            logger.info("🔄 Starting Synthetix Monitor...")
            monitor = SynthetixMonitor(env=args.env)
            prices = monitor.get_token_prices()
            wallet_addresses = os.getenv("WALLET_ADDRESSES", "").split(",")

            if not wallet_addresses[0]:
                logger.error("❌ No wallet addresses configured")
                return
            # wallet_addresses.insert(0, "0x0000000000000000000000000000000000000000")
            for wallet in wallet_addresses:
                logger.info(f"🔎 Checking wallet: {wallet}")
                positions = monitor.get_positions(wallet_address=wallet, prices=prices)
                # ic(pric
                ic(positions)
                if positions:
                    # Save to database
                    monitor.save_positions(wallet, positions)

                    # Log the positions
                    logger.info("🏦 Positions synthetix:")
                    logger.info("=============================================")
                    for pos in positions:
                        logger.info(f"""
                        💰 Token address: {pos["token"]}
                        📥 Amount: {Decimal(pos["amount"]) / Decimal(10**8)}
                        📥 Reward: {Decimal(pos["reward"])}
                        📈 pool id: {pos["pool_id"]}
                        📊 account_id: {pos["account_id"]}
                        """)
                else:
                    logger.info("Aucune position trouvée")

        except Exception as e:
            logger.error(f"❌ Erreur générale: {str(e)}")
        time.sleep(CHECK_INTERVAL)


def list_contract_functions(contract):
    functions = []
    for fn in contract.functions._functions:
        functions.append(fn)
    # ic("Available functions:", functions)


if __name__ == "__main__":
    # ic.disable()
    main()
