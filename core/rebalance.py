def compute_notional_exposure(contracts_held: int, point_value: float, price: float) -> float:
    return contracts_held * point_value * price


def compute_current_leverage(notional_exposure: float, equity: float) -> float:
    if equity == 0:
        return 0.0
    return notional_exposure / equity


def compute_target_contracts(target_leverage: float, equity: float, point_value: float, price: float) -> int:
    return round(target_leverage * equity / (point_value * price))


def should_rebalance(current_leverage: float, target_leverage: float, band: float = 0.2) -> bool:
    # Use small epsilon to handle floating point precision
    # abs(2.8 - 3.0) = 0.2000000000000001776... (due to float representation)
    # which is > 0.2, causing false positives at band edges
    return (abs(current_leverage - target_leverage) - band) > 1e-10


def mark_to_market_pnl(contracts_held: int, point_value: float, prior_price: float, current_price: float) -> float:
    return contracts_held * point_value * (current_price - prior_price)


def accrue_yield(equity: float, annual_rate_pct: float, calendar_days: int) -> float:
    return equity * (annual_rate_pct / 100.0) * (calendar_days / 365.0)


def update_equity(
    equity: float,
    contracts_held: int,
    point_value: float,
    prior_price: float,
    current_price: float,
    annual_rate_pct: float,
    calendar_days: int,
) -> float:
    pnl = mark_to_market_pnl(contracts_held, point_value, prior_price, current_price)
    yield_earned = accrue_yield(equity, annual_rate_pct, calendar_days)
    return equity + pnl + yield_earned


def margin_warning(
    notional_exposure: float,
    equity: float,
    approx_margin_rate: float = 0.10,
    warning_threshold: float = 0.5,
) -> bool:
    if equity <= 0:
        return True
    margin_used = notional_exposure * approx_margin_rate
    return (margin_used / equity) > warning_threshold
