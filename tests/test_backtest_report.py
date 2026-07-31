from compare.backtest_vs_tqqq import generate_report


def test_generate_report_formats_comparison_table():
    synthetic_metrics = {"cagr": 0.20, "max_drawdown": -0.55, "total_return": 5.0}
    tqqq_metrics = {"cagr": 0.15, "max_drawdown": -0.80, "total_return": 3.0}

    report = generate_report(synthetic_metrics, tqqq_metrics)

    expected = (
        "| Metric | Synthetic (Futures + Band Rebalance) | Actual TQQQ |\n"
        "| --- | ---: | ---: |\n"
        "| CAGR | 20.00% | 15.00% |\n"
        "| Max Drawdown | -55.00% | -80.00% |\n"
        "| Total Return | 500.00% | 300.00% |\n"
        "| Annualized Delta (synthetic - TQQQ) | +5.00% | |"
    )
    assert report == expected
