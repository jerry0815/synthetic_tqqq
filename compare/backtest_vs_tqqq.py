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


def compute_metrics(equity: pd.Series) -> dict:
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    max_drawdown = drawdown.min()
    return {"total_return": total_return, "cagr": cagr, "max_drawdown": max_drawdown}


def generate_report(synthetic_metrics: dict, tqqq_metrics: dict, num_rebalances: int) -> str:
    delta_cagr = synthetic_metrics["cagr"] - tqqq_metrics["cagr"]
    lines = [
        "| Metric | Synthetic (Futures + Band Rebalance) | Actual TQQQ |",
        "| --- | ---: | ---: |",
        f"| CAGR | {synthetic_metrics['cagr']*100:.2f}% | {tqqq_metrics['cagr']*100:.2f}% |",
        f"| Max Drawdown | {synthetic_metrics['max_drawdown']*100:.2f}% | {tqqq_metrics['max_drawdown']*100:.2f}% |",
        f"| Total Return | {synthetic_metrics['total_return']*100:.2f}% | {tqqq_metrics['total_return']*100:.2f}% |",
        f"| # Rebalance trades | {num_rebalances} | 0 |",
        f"| Annualized Delta (synthetic - TQQQ) | {delta_cagr*100:+.2f}% | |",
        "",
        (
            "The synthetic strategy only holds 3x exposure while trade_bot's SMA200+ATR "
            "S&P 500 signal is bullish, sitting in cash the rest of the time; TQQQ's "
            "buy-and-hold benchmark stays fully invested throughout. That signal-gating, "
            "plus the 0.2x rebalance band's looser tracking of daily leverage versus TQQQ's "
            "continuous daily reset, is the primary driver of the delta above — traded off "
            "against a shallower max drawdown."
        ),
    ]
    return "\n".join(lines)


def main():
    import os
    import sys

    import yfinance as yf

    trade_bot_path = os.environ.get(
        "TRADE_BOT_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "trade_bot"),
    )
    if trade_bot_path not in sys.path:
        sys.path.insert(0, trade_bot_path)
    from backtest.strat_backtest import SMATrendFollowing, get_cached_signals

    gspc = get_cached_signals("^GSPC", sma_window=200)
    strat = SMATrendFollowing(sma_window=200, t2_confirmation=True)
    gspc, _ = strat.generate_signals(gspc)

    nq = yf.download("NQ=F", start=TQQQ_INCEPTION, progress=False, auto_adjust=False)
    tqqq = yf.download("TQQQ", start=TQQQ_INCEPTION, progress=False, auto_adjust=False)
    irx = yf.download("^IRX", start=TQQQ_INCEPTION, progress=False, auto_adjust=False)
    for df in (nq, tqqq, irx):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

    common_index = gspc.index.intersection(nq.index).intersection(irx.index)
    common_index = common_index[common_index >= pd.Timestamp(TQQQ_INCEPTION)]

    prices = nq["Close"].reindex(common_index).ffill()
    in_market = gspc["in_market"].reindex(common_index).ffill()
    tbill = irx["Close"].reindex(common_index).ffill()

    result = simulate(prices, in_market, tbill, initial_equity=200000.0)
    synthetic_metrics = compute_metrics(result["equity"])

    tqqq_close = tqqq["Close"].reindex(common_index).ffill()
    tqqq_metrics = compute_metrics(tqqq_close)

    report = generate_report(synthetic_metrics, tqqq_metrics, int(result["rebalanced"].sum()))

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report + "\n")

    print(report)


if __name__ == "__main__":
    main()
