def wei_to_ether(wei_value: int) -> float:
    """
    Convert wei value to ether value::
    
        >>> wei_to_ether(1000000000000000000)
        1.0
    
    :param int wei_value: wei value to convert to ether
    :return: ether value
    :rtype: float
    """
    return wei_value / 1e18

def ether_to_wei(ether_value: float) -> int:
    """
    Convert ether value to wei value::

        >>> ether_to_wei(1.0)
        1000000000000000000
    
    :param float ether_value: ether value to convert to wei
    :return: wei value
    :rtype: int
    """
    return int(ether_value * 1e18)
