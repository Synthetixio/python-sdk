# 🔧 config.py
from dotenv import load_dotenv
import os

# Chargement des variables d'environnement
load_dotenv()

# Configuration
RPC_URL = os.getenv("RPC_URL", "https://mainnet.base.org")
WALLET_ADDRESSES = os.getenv("WALLET_ADDRESSES")


CHECK_INTERVAL = 1800

USDC_SYNTH_ADDRESS = "0xC74eA762cF06c9151cE074E6a569a5945b6302E7"
