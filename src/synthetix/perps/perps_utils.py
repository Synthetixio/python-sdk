from eth_utils import encode_hex

def unpack_bfp_configuration(config_data):
    """
    Unpacks the market configuration data returned by getMarketConfiguration.

    :param config_data: Tuple containing the raw configuration data
    :return: Dictionary with decoded configuration values
    """
    return {
        "pyth": config_data[0],
        "eth_oracle_node_id": config_data[1].hex(),
        "reward_distributor_implementation": config_data[2],
        "pyth_publish_time_min": config_data[3],
        "pyth_publish_time_max": config_data[4],
        "min_order_age": config_data[5],
        "max_order_age": config_data[6],
        "min_keeper_fee_usd": config_data[7],
        "max_keeper_fee_usd": config_data[8],
        "keeper_profit_margin_usd": config_data[9],
        "keeper_profit_margin_percent": config_data[10],
        "keeper_settlement_gas_units": config_data[11],
        "keeper_cancellation_gas_units": config_data[12],
        "keeper_liquidation_gas_units": config_data[13],
        "keeper_flag_gas_units": config_data[14],
        "keeper_liquidate_margin_gas_units": config_data[15],
        "keeper_liquidation_endorsed": config_data[16],
        "collateral_discount_scalar": config_data[17],
        "min_collateral_discount": config_data[18],
        "max_collateral_discount": config_data[19],
        "utilization_breakpoint_percent": config_data[20],
        "low_utilization_slope_percent": config_data[21],
        "high_utilization_slope_percent": config_data[22],
    }


def unpack_bfp_configuration_by_id(config_data):
    """
    Unpacks the market configuration data returned by getMarketConfigurationById.

    :param config_data: Tuple containing the raw configuration data
    :return: Dictionary with decoded configuration values
    """
    (
        oracle_node_id,
        pyth_price_feed_id,
        maker_fee,
        taker_fee,
        max_market_size,
        max_funding_velocity,
        skew_scale,
        funding_velocity_clamp,
        min_credit_percent,
        min_margin_usd,
        min_margin_ratio,
        incremental_margin_scalar,
        maintenance_margin_scalar,
        max_initial_margin_ratio,
        liquidation_reward_percent,
        liquidation_limit_scalar,
        liquidation_window_duration,
        liquidation_max_pd,
    ) = config_data

    return {
        "oracle_node_id": encode_hex(oracle_node_id),
        "pyth_price_feed_id": encode_hex(pyth_price_feed_id),
        "maker_fee": maker_fee,
        "taker_fee": taker_fee,
        "max_market_size": max_market_size,
        "max_funding_velocity": max_funding_velocity,
        "skew_scale": skew_scale,
        "funding_velocity_clamp": funding_velocity_clamp,
        "min_credit_percent": min_credit_percent,
        "min_margin_usd": min_margin_usd,
        "min_margin_ratio": min_margin_ratio,
        "incremental_margin_scalar": incremental_margin_scalar,
        "maintenance_margin_scalar": maintenance_margin_scalar,
        "max_initial_margin_ratio": max_initial_margin_ratio,
        "liquidation_reward_percent": liquidation_reward_percent,
        "liquidation_limit_scalar": liquidation_limit_scalar,
        "liquidation_window_duration": liquidation_window_duration,
        "liquidation_max_pd": liquidation_max_pd,
    }
