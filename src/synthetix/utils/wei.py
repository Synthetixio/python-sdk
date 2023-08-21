def wei_to_ether(wei_value: int) -> float:
    return wei_value / 1e18

def ether_to_wei(ether_value: float) -> int:
    return int(ether_value * 1e18)
