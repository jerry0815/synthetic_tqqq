from compare.backtest_vs_tqqq import generate_report


def test_generate_report_formats_comparison_table():
    synthetic_metrics = {"cagr": 0.20, "max_drawdown": -0.55, "total_return": 5.0}
    tqqq_metrics = {"cagr": 0.15, "max_drawdown": -0.80, "total_return": 3.0}

    report = generate_report(synthetic_metrics, tqqq_metrics, num_rebalances=42)

    expected = (
        "| Metric | Synthetic (Futures + Band Rebalance) | Actual TQQQ |\n"
        "| --- | ---: | ---: |\n"
        "| CAGR | 20.00% | 15.00% |\n"
        "| Max Drawdown | -55.00% | -80.00% |\n"
        "| Total Return | 500.00% | 300.00% |\n"
        "| # Rebalance trades | 42 | 0 |\n"
        "| Annualized Delta (synthetic - TQQQ) | +5.00% | |\n"
        "\n"
        "The synthetic strategy only holds 3x exposure while trade_bot's SMA200+ATR "
        "S&P 500 signal is bullish, sitting in cash the rest of the time; TQQQ's "
        "buy-and-hold benchmark stays fully invested throughout. That signal-gating, "
        "plus the 0.2x rebalance band's looser tracking of daily leverage versus TQQQ's "
        "continuous daily reset, is the primary driver of the delta above — traded off "
        "against a shallower max drawdown."
    )
    assert report == expected
