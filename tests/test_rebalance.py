import pytest

from core import rebalance


def test_compute_notional_exposure():
    assert rebalance.compute_notional_exposure(10, 2.0, 20000.0) == 400000.0


def test_compute_current_leverage():
    assert rebalance.compute_current_leverage(400000.0, 200000.0) == 2.0


def test_compute_current_leverage_zero_equity_returns_zero():
    assert rebalance.compute_current_leverage(400000.0, 0.0) == 0.0


def test_compute_target_contracts_rounds_to_nearest_whole_contract():
    assert rebalance.compute_target_contracts(3.0, 200000.0, 2.0, 20000.0) == 15


def test_should_rebalance_true_when_drift_exceeds_band():
    assert rebalance.should_rebalance(2.0, 3.0, band=0.2) is True


def test_should_rebalance_false_exactly_at_band_edge():
    assert rebalance.should_rebalance(2.8, 3.0, band=0.2) is False


def test_should_rebalance_true_just_past_band_edge():
    assert rebalance.should_rebalance(2.7999, 3.0, band=0.2) is True


def test_mark_to_market_pnl():
    assert rebalance.mark_to_market_pnl(10, 2.0, 20000.0, 20100.0) == 2000.0


def test_mark_to_market_pnl_negative_price_move():
    assert rebalance.mark_to_market_pnl(10, 2.0, 20100.0, 20000.0) == -2000.0


def test_accrue_yield():
    expected = 200000.0 * 0.05 * (1 / 365)
    assert rebalance.accrue_yield(200000.0, 5.0, 1) == pytest.approx(expected)


def test_update_equity_combines_pnl_and_yield():
    expected = 200000.0 + 2000.0 + (200000.0 * 0.05 * (1 / 365))
    result = rebalance.update_equity(200000.0, 10, 2.0, 20000.0, 20100.0, 5.0, 1)
    assert result == pytest.approx(expected)


def test_margin_warning_false_when_under_threshold():
    assert rebalance.margin_warning(400000.0, 200000.0, approx_margin_rate=0.10, warning_threshold=0.5) is False


def test_margin_warning_true_when_over_threshold():
    assert rebalance.margin_warning(1200000.0, 200000.0, approx_margin_rate=0.10, warning_threshold=0.5) is True
