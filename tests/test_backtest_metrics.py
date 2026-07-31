import pandas as pd
import pytest

from compare.backtest_vs_tqqq import compute_metrics


def test_compute_metrics_total_return_and_cagr():
    dates = pd.to_datetime(["2021-01-01", "2022-01-01"])
    equity = pd.Series([100000.0, 121000.0], index=dates)

    metrics = compute_metrics(equity)

    assert metrics["total_return"] == pytest.approx(0.21)
    years = (dates[-1] - dates[0]).days / 365.25
    expected_cagr = (121000.0 / 100000.0) ** (1 / years) - 1
    assert metrics["cagr"] == pytest.approx(expected_cagr)


def test_compute_metrics_max_drawdown():
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    equity = pd.Series([100000.0, 120000.0, 90000.0, 110000.0], index=dates)

    metrics = compute_metrics(equity)

    assert metrics["max_drawdown"] == pytest.approx(90000.0 / 120000.0 - 1)
