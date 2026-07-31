"""One-off validation: does the futures-replication mechanics alone (no SMA
signal gating, daily rebalance back to exactly 3.0x) reproduce TQQQ's actual
returns? This isolates the core replication math from the signal-gating and
0.2x band tolerance that backtest_vs_tqqq.py's main() applies on top -
answering "can this approach even track TQQQ" before trusting the fancier
signal-gated comparison.

Run: python -m compare.validate_daily_rebalance
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

    # band=0.0 -> should_rebalance fires on any non-negligible drift, i.e.
    # rebalance back to exactly 3.0x leverage every single day.
    result = simulate(prices, in_market, tbill, initial_equity=200000.0, band=0.0)
    metrics = compute_metrics(result["equity"])

    tqqq_close = tqqq["Close"].reindex(common_index).ffill()
    tqqq_metrics = compute_metrics(tqqq_close)

    print(f"Days simulated: {len(result)}")
    print(f"Rebalances: {int(result['rebalanced'].sum())} ({int(result['rebalanced'].sum()) / len(result) * 100:.1f}% of days)")
    print()
    print("Synthetic (Buy & Hold, daily rebalance to 3.0x):")
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
