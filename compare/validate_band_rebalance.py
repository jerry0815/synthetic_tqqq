"""One-off validation: how much does the 0.2x band tolerance alone cost
versus daily rebalancing, when SMA signal-gating is removed entirely (Buy &
Hold, always invested)? Companion to validate_daily_rebalance.py - that
script isolates the replication mechanics with band=0.0 (rebalance every
day); this one isolates the band-tolerance effect by using the project's
real 0.2x band with the same always-invested assumption, so the delta
between the two runs is attributable to the band alone, not signal-gating.

Run: python -m compare.validate_band_rebalance
"""
import pandas as pd
import yfinance as yf

from compare.backtest_vs_tqqq import TQQQ_INCEPTION, compute_metrics, simulate


def main():
    nq = yf.download("NQ=F", start=TQQQ_INCEPTION, progress=False, auto_adjust=False)
    tqqq = yf.download("TQQQ", start=TQQQ_INCEPTION, progress=False, auto_adjust=False)
    irx = yf.download("^IRX", start=TQQQ_INCEPTION, progress=False, auto_adjust=False)
    for df in (nq, tqqq, irx):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

    common_index = nq.index.intersection(irx.index)
    common_index = common_index[common_index >= pd.Timestamp(TQQQ_INCEPTION)]

    prices = nq["Close"].reindex(common_index).ffill()
    tbill = irx["Close"].reindex(common_index).ffill()
    # Buy & Hold: always invested, no SMA signal gating.
    in_market = pd.Series(True, index=common_index)

    # band=0.2 -> the project's real rebalance band: only trade when
    # drift from 3.0x exceeds 0.2x, same tolerance used in bot.py/main().
    result = simulate(prices, in_market, tbill, initial_equity=200000.0, band=0.2)
    metrics = compute_metrics(result["equity"])

    tqqq_close = tqqq["Close"].reindex(common_index).ffill()
    tqqq_metrics = compute_metrics(tqqq_close)

    print(f"Days simulated: {len(result)}")
    print(f"Rebalances: {int(result['rebalanced'].sum())} ({int(result['rebalanced'].sum()) / len(result) * 100:.1f}% of days)")
    print()
    print("Synthetic (Buy & Hold, 0.2x band rebalance):")
    print(f"  CAGR:         {metrics['cagr']*100:.2f}%")
    print(f"  Max Drawdown: {metrics['max_drawdown']*100:.2f}%")
    print(f"  Total Return: {metrics['total_return']*100:.2f}%")
    print()
    print("TQQQ (actual):")
    print(f"  CAGR:         {tqqq_metrics['cagr']*100:.2f}%")
    print(f"  Max Drawdown: {tqqq_metrics['max_drawdown']*100:.2f}%")
    print(f"  Total Return: {tqqq_metrics['total_return']*100:.2f}%")
    print()
    print(f"Annualized Delta (synthetic - TQQQ): {(metrics['cagr'] - tqqq_metrics['cagr'])*100:+.2f}pp")


if __name__ == "__main__":
    main()
