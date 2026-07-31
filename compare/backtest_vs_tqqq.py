"""One-off report: compares this project's band-rebalanced synthetic 3x QQQ
(via NQ futures) against actually holding TQQQ, since TQQQ's 2010-02-11
inception. Not part of the daily bot — run manually with
`python -m compare.backtest_vs_tqqq`."""
import pandas as pd

from core import rebalance

POINT_VALUE = 2.0
TQQQ_INCEPTION = "2010-02-11"


def simulate(
    prices: pd.Series,
    in_market: pd.Series,
    tbill_rates: pd.Series,
    initial_equity: float = 200000.0,
    point_value: float = POINT_VALUE,
    target_leverage_when_in: float = 3.0,
    band: float = 0.2,
) -> pd.DataFrame:
    equity = initial_equity
    contracts_held = 0
    prior_price = None
    prior_date = None
    rows = []

    for date in prices.index:
        price = float(prices.loc[date])
        rate = float(tbill_rates.loc[date])

        if prior_price is not None:
            calendar_days = (date - prior_date).days
            equity = rebalance.update_equity(
                equity, contracts_held, point_value, prior_price, price, rate, calendar_days,
            )

        target_leverage = target_leverage_when_in if bool(in_market.loc[date]) else 0.0
        notional = rebalance.compute_notional_exposure(contracts_held, point_value, price)
        current_leverage = rebalance.compute_current_leverage(notional, equity)
        rebalanced = rebalance.should_rebalance(current_leverage, target_leverage, band)

        if rebalanced:
            contracts_held = rebalance.compute_target_contracts(target_leverage, equity, point_value, price)
            notional = rebalance.compute_notional_exposure(contracts_held, point_value, price)
            current_leverage = rebalance.compute_current_leverage(notional, equity)

        rows.append({
            "date": date,
            "equity": equity,
            "contracts_held": contracts_held,
            "notional": notional,
            "current_leverage": current_leverage,
            "target_leverage": target_leverage,
            "rebalanced": rebalanced,
        })

        prior_price = price
        prior_date = date

    return pd.DataFrame(rows).set_index("date")
