from decimal import Decimal

def wei_to_ether(wei_value: int) -> float:
    """
    Convert wei value to ether value::
    
        >>> wei_to_ether(1000000000000000000)
        1.0
    
    :param int wei_value: wei value to convert to ether
    :return: ether value
    :rtype: float
    """
    wei_value = Decimal(str(wei_value))
    ether_value = wei_value / Decimal("1e18")
    return float(ether_value)

def ether_to_wei(ether_value: float) -> int:
    """
    Convert ether value to wei value::

        >>> ether_to_wei(1.0)
        1000000000000000000
    
    :param float ether_value: ether value to convert to wei
    :return: wei value
    :rtype: int
    """
    ether_value = Decimal(str(ether_value))
    wei_value = ether_value * Decimal("1e18")
    return int(wei_value)
