import datetime as dt

import numpy as np

MNQ_POINT_VALUE = 2.0
QUARTER_MONTHS = [3, 6, 9, 12]
MONTH_CODES = {3: "H", 6: "M", 9: "U", 12: "Z"}


def third_friday(year: int, month: int) -> dt.date:
    """Return the date of the 3rd Friday of the given month/year."""
    first_of_month = dt.date(year, month, 1)
    friday_offset = (4 - first_of_month.weekday()) % 7  # Monday=0 ... Friday=4
    first_friday = first_of_month + dt.timedelta(days=friday_offset)
    return first_friday + dt.timedelta(weeks=2)


def contract_symbol(year: int, month: int) -> str:
    """e.g. contract_symbol(2025, 12) -> 'MNQZ25'."""
    code = MONTH_CODES[month]
    two_digit_year = f"{year % 100:02d}"
    return f"MNQ{code}{two_digit_year}"


def next_quarterly_month(year: int, month: int):
    idx = QUARTER_MONTHS.index(month)
    if idx == len(QUARTER_MONTHS) - 1:
        return (year + 1, QUARTER_MONTHS[0])
    return (year, QUARTER_MONTHS[idx + 1])


def current_contract_month(as_of: dt.date):
    """Return (year, month) of the currently active quarterly contract as of as_of:
    the nearest quarter whose 3rd-Friday expiry is still on/after as_of."""
    year = as_of.year
    for month in QUARTER_MONTHS:
        if third_friday(year, month) >= as_of:
            return (year, month)
    return (year + 1, QUARTER_MONTHS[0])


def trading_days_until(as_of: dt.date, target: dt.date) -> int:
    """Business-day count (Mon-Fri) from as_of up to but not including target.
    Does not account for exchange holidays (documented simplification)."""
    if target <= as_of:
        return 0
    return int(np.busday_count(as_of, target))


def roll_status(as_of: dt.date, contract_year: int, contract_month: int, roll_offset_trading_days: int = 5) -> dict:
    """Return roll status info for the given quarterly contract as of a date."""
    expiry = third_friday(contract_year, contract_month)
    trading_days_left = trading_days_until(as_of, expiry)
    should_roll = trading_days_left <= roll_offset_trading_days
    next_year, next_month = next_quarterly_month(contract_year, contract_month)
    return {
        "expiry": expiry,
        "trading_days_left": trading_days_left,
        "should_roll": should_roll,
        "current_symbol": contract_symbol(contract_year, contract_month),
        "next_symbol": contract_symbol(next_year, next_month),
        "next_year": next_year,
        "next_month": next_month,
    }
