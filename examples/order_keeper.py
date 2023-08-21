import os
import asyncio
from synthetix import Synthetix
from dotenv import load_dotenv
import concurrent.futures

load_dotenv()

PROVIDER_RPC_URL = os.environ.get('TESTNET_RPC')
ADDRESS = os.environ.get('ADDRESS')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')


class Keeper:
    def __init__(self):
        self.snx = Synthetix(
            provider_rpc=PROVIDER_RPC_URL,
            private_key=PRIVATE_KEY,
            address=ADDRESS,
            network_id=420,
        )

    def process_event(self, event):
        # extract the required information from the event
        account_id = event["args"]["accountId"]
        market_id = event["args"]["marketId"]
        market_name = self.snx.perps.markets_by_id[market_id]["market_name"]

        self.snx.logger.info(f'Settling order for {account_id} for market {market_name}')
        self.snx.perps.settle_pyth_order(account_id, submit=True)

    async def monitor_events(self):
        event_filter = self.snx.perps.market_proxy.events.OrderCommitted.create_filter(fromBlock="latest")

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:

            while True:
                self.snx.logger.info('Checking for new orders')
                try:
                    events = event_filter.get_new_entries()

                    for event in events:
                        loop.run_in_executor(executor, self.process_event, event)
                except Exception as e:
                    print(e)

                self.snx.logger.info(f'{len(events)} orders processed, waiting for new orders')
                await asyncio.sleep(15)  # Adjust the sleep time as needed


async def main():
    keeper = Keeper()
    await keeper.monitor_events()

if __name__ == "__main__":
    asyncio.run(main())
