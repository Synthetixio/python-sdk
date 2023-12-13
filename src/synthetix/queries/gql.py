from gql import gql

candles = gql(
    """
    query(
        $last_id: ID!
        $asset: String!
        $min_timestamp: BigInt = 0
        $max_timestamp: BigInt!
        $period: BigInt!
    ) {
        candles (
            where: {
                id_gt: $last_id
                synth: $asset
                timestamp_gt: $min_timestamp
                timestamp_lt: $max_timestamp
                period: $period
            }
            first: 1000
        ) {
            id
            synth
            open
            high
            low
            close
            timestamp
            average
            period
            aggregatedPrices
        }
    }
"""
)

transfers = gql(
    """
    query(
        $last_id: ID!
        $min_timestamp: BigInt = 0
        $max_timestamp: BigInt!
    ) {
        futuresMarginTransfers (
            where: {
                id_gt: $last_id
                timestamp_gt: $min_timestamp
                timestamp_lt: $max_timestamp
            }
            first: 1000
        ) {
            id,
            account,
            timestamp,
            asset,
            size,
            market,
            txHash
        }
    }
"""
)

transfers_market = gql(
    """
    query(
        $last_id: ID!
        $market_keys: [Bytes!]
        $min_timestamp: BigInt = 0
        $max_timestamp: BigInt!
    ) {
        futuresMarginTransfers (
            where: {
                id_gt: $last_id
                marketKey_in: $market_keys
                timestamp_gt: $min_timestamp
                timestamp_lt: $max_timestamp
            }
            first: 1000
        ) {
            id,
            account,
            timestamp,
            asset,
            size,
            market,
            txHash
        }
    }
"""
)

transfers_account = gql(
    """
    query(
        $last_id: ID!
        $account: Bytes!
        $min_timestamp: BigInt = 0
        $max_timestamp: BigInt!
    ) {
        futuresMarginTransfers (
            where: {
                id_gt: $last_id
                account: $account
                timestamp_gt: $min_timestamp
                timestamp_lt: $max_timestamp
            }
            first: 1000
        ) {
            id,
            account,
            timestamp,
            asset,
            size,
            market,
            txHash
        }
    }
"""
)

trades_account = gql(
    """
    query(
        $last_id: ID!
        $account: Bytes!
        $min_timestamp: BigInt = 0
        $max_timestamp: BigInt!
    ) {
        futuresTrades (
            where: {
                id_gt: $last_id
                account: $account
                timestamp_gt: $min_timestamp
                timestamp_lt: $max_timestamp
            }
            first: 1000
        ) {
			id
			timestamp
			account
			abstractAccount
			accountType
			margin
			size
			marketKey
			asset
			price
			positionId
			positionSize
			positionClosed
			pnl
			feesPaid
			keeperFeesPaid
			orderType
			trackingCode
			fundingAccrued
        }
    }
"""
)

trades_market = gql(
    """
    query(
        $last_id: ID!
        $market_keys: [Bytes!]
        $min_timestamp: BigInt = 0
        $max_timestamp: BigInt!
    ) {
        futuresTrades (
            where: {
                id_gt: $last_id
                marketKey_in: $market_keys
                timestamp_gt: $min_timestamp
                timestamp_lt: $max_timestamp
            }
            first: 1000
        ) {
			id
			timestamp
			account
			abstractAccount
			accountType
			margin
			size
			marketKey
			asset
			price
			positionId
			positionSize
			positionClosed
			pnl
			feesPaid
			keeperFeesPaid
			orderType
			trackingCode
			fundingAccrued
        }
    }
"""
)

positions_market = gql(
    """
    query(
        $last_id: ID!
        $market_keys: [Bytes!]
        $is_open: [Boolean!]
    ) {
        futuresPositions (
            where: {
                id_gt: $last_id
                marketKey_in: $market_keys
                isOpen_in: $is_open
            }
            first: 1000
        ) {
			id
			lastTxHash
			openTimestamp
			closeTimestamp
			timestamp
			market
			marketKey
			asset
			account
			abstractAccount
			accountType
			isOpen
			isLiquidated
			trades
			totalVolume
			size
			initialMargin
			margin
			pnl
			feesPaid
			netFunding
			pnlWithFeesPaid
			netTransfers
			totalDeposits
			fundingIndex
			entryPrice
			avgEntryPrice
			lastPrice
			exitPrice
        }
    }
"""
)

positions_account = gql(
    """
    query(
        $last_id: ID!
        $account: Bytes!
        $is_open: [Boolean!]
    ) {
        futuresPositions (
            where: {
                id_gt: $last_id
                account: $account
                isOpen_in: $is_open
            }
            first: 1000
        ) {
			id
			lastTxHash
			openTimestamp
			closeTimestamp
			timestamp
			market
			marketKey
			asset
			account
			abstractAccount
			accountType
			isOpen
			isLiquidated
			trades
			totalVolume
			size
			initialMargin
			margin
			pnl
			feesPaid
			netFunding
			pnlWithFeesPaid
			netTransfers
			totalDeposits
			fundingIndex
			entryPrice
			avgEntryPrice
			lastPrice
			exitPrice
        }
    }
"""
)

funding_rates = gql(
    """
    query(
        $last_id: ID!
        $market_keys: [Bytes!]
        $min_timestamp: BigInt = 0
        $max_timestamp: BigInt!
    ) {
        fundingRateUpdates (
            where: {
                id_gt: $last_id
                marketKey_in: $market_keys
                timestamp_gt: $min_timestamp
                timestamp_lt: $max_timestamp
            }
            first: 1000
        ) {
            sequenceLength
            timestamp
            marketKey
            market
            id
            fundingRate
            funding
            asset
        }
    }
"""
)

queries = {
    "candles": candles,
    "transfers": transfers,
    "transfers_account": transfers_account,
    "transfers_market": transfers_market,
    "trades_account": trades_account,
    "trades_market": trades_market,
    "positions_account": positions_account,
    "positions_market": positions_market,
    "funding_rates": funding_rates,
}
