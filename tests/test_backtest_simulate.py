import pandas as pd
import pytest

from compare.backtest_vs_tqqq import simulate


def test_simulate_tracks_equity_and_contracts_through_signal_flip():
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    prices = pd.Series([20000.0, 20100.0, 20100.0, 25000.0], index=dates)
    in_market = pd.Series([True, True, False, False], index=dates)
    tbill = pd.Series([0.0, 0.0, 0.0, 0.0], index=dates)

    result = simulate(prices, in_market, tbill, initial_equity=200000.0)

    assert result["equity"].tolist() == pytest.approx([200000.0, 203000.0, 203000.0, 203000.0])
    assert result["contracts_held"].tolist() == [15, 15, 0, 0]
    assert result["rebalanced"].tolist() == [True, False, True, False]
    assert result["target_leverage"].tolist() == [3.0, 3.0, 0.0, 0.0]
