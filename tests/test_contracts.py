import datetime as dt

from core import contracts


def test_third_friday_of_december_2025():
    assert contracts.third_friday(2025, 12) == dt.date(2025, 12, 19)


def test_contract_symbol_formats_month_code_and_two_digit_year():
    assert contracts.contract_symbol(2025, 12) == "MNQZ25"
    assert contracts.contract_symbol(2026, 3) == "MNQH26"


def test_next_quarterly_month_rolls_within_year():
    assert contracts.next_quarterly_month(2025, 9) == (2025, 12)


def test_next_quarterly_month_rolls_into_next_year():
    assert contracts.next_quarterly_month(2025, 12) == (2026, 3)


def test_current_contract_month_before_expiry_stays_on_same_contract():
    assert contracts.current_contract_month(dt.date(2025, 11, 1)) == (2025, 12)


def test_current_contract_month_after_expiry_rolls_to_next_year():
    assert contracts.current_contract_month(dt.date(2025, 12, 20)) == (2026, 3)


def test_trading_days_until_counts_business_days_excluding_target():
    assert contracts.trading_days_until(dt.date(2025, 12, 1), dt.date(2025, 12, 19)) == 14


def test_trading_days_until_returns_zero_when_target_not_in_future():
    assert contracts.trading_days_until(dt.date(2025, 12, 19), dt.date(2025, 12, 19)) == 0


def test_roll_status_far_from_expiry_does_not_flag_roll():
    status = contracts.roll_status(dt.date(2025, 12, 1), 2025, 12, roll_offset_trading_days=5)
    assert status["should_roll"] is False
    assert status["trading_days_left"] == 14
    assert status["current_symbol"] == "MNQZ25"
    assert status["next_symbol"] == "MNQH26"
    assert status["expiry"] == dt.date(2025, 12, 19)


def test_roll_status_within_offset_window_flags_roll():
    status = contracts.roll_status(dt.date(2025, 12, 15), 2025, 12, roll_offset_trading_days=5)
    assert status["trading_days_left"] == 4
    assert status["should_roll"] is True
