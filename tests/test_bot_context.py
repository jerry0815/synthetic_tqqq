import datetime as dt

import pytest

import bot
from core import ledger


def test_build_context_first_run_targets_full_leverage_from_flat():
    state = dict(ledger.DEFAULT_STATE)
    price_info = {"price": 20000.0, "annual_rate_pct": 5.0, "date": dt.date(2026, 7, 30)}
    signal_stats = {"action": "BUY/HOLD"}

    ctx = bot.build_context(state, price_info, signal_stats, dt.date(2026, 7, 30))

    assert ctx["equity"] == 200000.0
    assert ctx["contracts_held"] == 0
    assert ctx["notional"] == 0.0
    assert ctx["current_leverage"] == 0.0
    assert ctx["target_leverage"] == 3.0
    assert ctx["rebalance_needed"] is True
    assert ctx["target_contracts"] == 15
    assert ctx["delta_contracts"] == 15
    assert ctx["margin_flag"] is False
    assert ctx["new_state"] == {
        "contracts_held": 15,
        "contract_year": 2026,
        "contract_month": 9,
        "equity": 200000.0,
        "last_price": 20000.0,
        "last_run_date": "2026-07-30",
    }


def test_build_context_within_band_holds_and_accrues_pnl_and_yield():
    state = {
        "contracts_held": 15,
        "contract_year": 2026,
        "contract_month": 9,
        "equity": 200000.0,
        "last_price": 20000.0,
        "last_run_date": "2026-07-30",
    }
    price_info = {"price": 20050.0, "annual_rate_pct": 5.0, "date": dt.date(2026, 7, 31)}
    signal_stats = {"action": "BUY/HOLD"}

    ctx = bot.build_context(state, price_info, signal_stats, dt.date(2026, 7, 31))

    expected_pnl = 15 * 2.0 * (20050.0 - 20000.0)
    expected_yield = 200000.0 * 0.05 * (1 / 365)
    expected_equity = 200000.0 + expected_pnl + expected_yield
    expected_notional = 15 * 2.0 * 20050.0
    expected_leverage = expected_notional / expected_equity

    assert ctx["equity"] == pytest.approx(expected_equity)
    assert ctx["notional"] == pytest.approx(expected_notional)
    assert ctx["current_leverage"] == pytest.approx(expected_leverage)
    assert ctx["rebalance_needed"] is False
    assert ctx["delta_contracts"] == 0
    assert ctx["new_state"]["contracts_held"] == 15


def test_build_context_sell_signal_flattens_position():
    state = {
        "contracts_held": 15,
        "contract_year": 2026,
        "contract_month": 9,
        "equity": 200000.0,
        "last_price": 20050.0,
        "last_run_date": "2026-07-31",
    }
    price_info = {"price": 20050.0, "annual_rate_pct": 0.0, "date": dt.date(2026, 8, 1)}
    signal_stats = {"action": "SELL/CASH"}

    ctx = bot.build_context(state, price_info, signal_stats, dt.date(2026, 8, 1))

    assert ctx["target_leverage"] == 0.0
    assert ctx["rebalance_needed"] is True
    assert ctx["target_contracts"] == 0
    assert ctx["delta_contracts"] == -15
    assert ctx["margin_flag"] is False
    assert ctx["new_state"]["contracts_held"] == 0


def test_build_context_within_roll_offset_window_rolls_contract_month():
    state = {
        "contracts_held": 10,
        "contract_year": 2026,
        "contract_month": 9,
        "equity": 200000.0,
        "last_price": 20000.0,
        "last_run_date": "2026-09-10",
    }
    price_info = {"price": 20000.0, "annual_rate_pct": 0.0, "date": dt.date(2026, 9, 11)}
    signal_stats = {"action": "BUY/HOLD"}

    ctx = bot.build_context(state, price_info, signal_stats, dt.date(2026, 9, 11))

    assert ctx["roll"]["should_roll"] is True
    assert ctx["delta_contracts"] == 5
    assert ctx["new_state"]["contracts_held"] == 15
    assert ctx["new_state"]["contract_year"] == 2026
    assert ctx["new_state"]["contract_month"] == 12
