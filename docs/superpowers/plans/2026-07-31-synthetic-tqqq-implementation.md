# Synthetic 3x QQQ Futures Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a notify-only Discord bot that tracks a synthetic 3x-leveraged QQQ position held via MNQ (Micro E-mini Nasdaq-100) futures, recommending band-rebalance trades (0.2x drift band around a 3.0x/0.0x target driven by trade_bot's SMA signal) and contract rolls, plus a one-off backtest comparing this approach's historical performance against holding TQQQ directly.

**Architecture:** Pure-function core modules (`core/contracts.py`, `core/rebalance.py`, `core/ledger.py`) handle all math and state with no I/O, so they're fully unit-testable without network access. `core/pricing.py` and `core/signal.py` wrap the only two network/cross-repo dependencies (yfinance, trade_bot's `SMATrendFollowing`). `bot.py` composes these into a daily context (`build_context`) and a Discord message (`format_discord_message`), mirroring trade_bot's own `bot.py` shape. `compare/backtest_vs_tqqq.py` reuses the same `core.rebalance` functions to simulate the strategy historically against NQ=F price history and reports the delta vs actual TQQQ returns.

**Tech Stack:** Python 3.9+, `yfinance`, `pandas`, `numpy`, `requests`, `pytest` for tests. Reuses `trade_bot`'s `backtest/strat_backtest.py` (`SMATrendFollowing`, `get_cached_signals`) as an external dependency, checked out alongside this repo in CI.

## Global Constraints

- Initial capital: $200,000 (only used as the starting `equity` value on first run / start of backtest).
- MNQ point value: $2.00 per index point.
- Target leverage: 3.0x when trade_bot's signal is `BUY/HOLD`, 0.0x when `SELL/CASH`.
- Rebalance band: trigger a rebalance only when `abs(current_leverage - target_leverage) > 0.2`.
- Roll reminder offset: 5 trading days before quarterly expiry (configurable, business-day count, does not account for exchange holidays — documented simplification).
- Margin warning: informational only, never blocks a recommendation. Approximated as `notional_exposure * 0.10` (10% approx margin rate) compared against a configurable 50%-of-equity warning threshold.
- No automated trade execution anywhere in this project — every action is a Discord notification the user executes manually.
- No commission/slippage modeling in the backtest.
- `current_price` is always that trading day's closing price (the bot runs after US market close), used as a same-day settlement approximation for both mark-to-market and any recommended trade's simulated fill price.
- trade_bot (`jerry0815/trade_bot`) is public on GitHub — CI accesses it via a second `actions/checkout` step, no PAT required.
- Signal source: `SMATrendFollowing(sma_window=200, t2_confirmation=True).get_live_stats("SPY", "SPY")['action']` from trade_bot's `backtest/strat_backtest.py` — this is the same S&P 500-driven signal trade_bot's own `bot.py` surfaces as `RECOMMENDED ACTION`.
- Backtest futures proxy: NQ=F (full-size E-mini) continuous price series, not MNQ=F, since MNQ only launched May 2019 and NQ=F has data back to TQQQ's 2010-02-11 inception. Contract size doesn't affect the % return simulation.
- All test commands are run as `python -m pytest <path> -v` from the `synthetic_tqqq/` directory root (not bare `pytest`) — this reliably puts the project root on `sys.path` so `from core import ...` and `from compare... import ...` resolve.

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `core/__init__.py`
- Create: `compare/__init__.py`

**Interfaces:**
- Produces: `core` and `compare` as importable Python packages for all later tasks.

- [ ] **Step 1: Create `requirements.txt`**

```
yfinance
pandas
numpy
requests
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
trade_bot/
```

(`trade_bot/` is ignored because CI checks trade_bot out into a subfolder here — see Task 9 — and it must never be committed into this repo.)

- [ ] **Step 3: Create `core/__init__.py`** (empty file)

- [ ] **Step 4: Create `compare/__init__.py`** (empty file)

- [ ] **Step 5: Verify pytest is available**

Run: `python -m pytest --version`
Expected: prints a pytest version (install with `pip install pytest` first if missing — not added to `requirements.txt` since it's a dev-only tool, matching trade_bot's convention).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore core/__init__.py compare/__init__.py
git commit -m "chore: scaffold synthetic_tqqq project structure"
```

---

### Task 2: `core/contracts.py` — contract specs, expiry calendar, roll logic

**Files:**
- Create: `core/contracts.py`
- Test: `tests/test_contracts.py`

**Interfaces:**
- Produces: `MNQ_POINT_VALUE` (float), `QUARTER_MONTHS` (list[int]), `third_friday(year, month) -> date`, `contract_symbol(year, month) -> str`, `next_quarterly_month(year, month) -> (int, int)`, `current_contract_month(as_of: date) -> (int, int)`, `trading_days_until(as_of: date, target: date) -> int`, `roll_status(as_of, contract_year, contract_month, roll_offset_trading_days=5) -> dict` with keys `expiry` (date), `trading_days_left` (int), `should_roll` (bool), `current_symbol` (str), `next_symbol` (str), `next_year` (int), `next_month` (int).

- [ ] **Step 1: Write failing tests**

Create `tests/test_contracts.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_contracts.py -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError` (`core.contracts` doesn't exist yet).

- [ ] **Step 3: Implement `core/contracts.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_contracts.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add core/contracts.py tests/test_contracts.py
git commit -m "feat: add MNQ contract spec, expiry calendar, and roll-status logic"
```

---

### Task 3: `core/rebalance.py` — leverage math

**Files:**
- Create: `core/rebalance.py`
- Test: `tests/test_rebalance.py`

**Interfaces:**
- Consumes: nothing from other core modules (pure math on primitives).
- Produces: `compute_notional_exposure(contracts_held, point_value, price) -> float`, `compute_current_leverage(notional_exposure, equity) -> float`, `compute_target_contracts(target_leverage, equity, point_value, price) -> int`, `should_rebalance(current_leverage, target_leverage, band=0.2) -> bool`, `mark_to_market_pnl(contracts_held, point_value, prior_price, current_price) -> float`, `accrue_yield(equity, annual_rate_pct, calendar_days) -> float`, `update_equity(equity, contracts_held, point_value, prior_price, current_price, annual_rate_pct, calendar_days) -> float`, `margin_warning(notional_exposure, equity, approx_margin_rate=0.10, warning_threshold=0.5) -> bool`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_rebalance.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_rebalance.py -v`
Expected: FAIL with `ModuleNotFoundError` (`core.rebalance` doesn't exist yet).

- [ ] **Step 3: Implement `core/rebalance.py`**

```python
def compute_notional_exposure(contracts_held: int, point_value: float, price: float) -> float:
    return contracts_held * point_value * price


def compute_current_leverage(notional_exposure: float, equity: float) -> float:
    if equity == 0:
        return 0.0
    return notional_exposure / equity


def compute_target_contracts(target_leverage: float, equity: float, point_value: float, price: float) -> int:
    return round(target_leverage * equity / (point_value * price))


def should_rebalance(current_leverage: float, target_leverage: float, band: float = 0.2) -> bool:
    return abs(current_leverage - target_leverage) > band


def mark_to_market_pnl(contracts_held: int, point_value: float, prior_price: float, current_price: float) -> float:
    return contracts_held * point_value * (current_price - prior_price)


def accrue_yield(equity: float, annual_rate_pct: float, calendar_days: int) -> float:
    return equity * (annual_rate_pct / 100.0) * (calendar_days / 365.0)


def update_equity(
    equity: float,
    contracts_held: int,
    point_value: float,
    prior_price: float,
    current_price: float,
    annual_rate_pct: float,
    calendar_days: int,
) -> float:
    pnl = mark_to_market_pnl(contracts_held, point_value, prior_price, current_price)
    yield_earned = accrue_yield(equity, annual_rate_pct, calendar_days)
    return equity + pnl + yield_earned


def margin_warning(
    notional_exposure: float,
    equity: float,
    approx_margin_rate: float = 0.10,
    warning_threshold: float = 0.5,
) -> bool:
    if equity <= 0:
        return True
    margin_used = notional_exposure * approx_margin_rate
    return (margin_used / equity) > warning_threshold
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_rebalance.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add core/rebalance.py tests/test_rebalance.py
git commit -m "feat: add leverage/equity math (mark-to-market pnl, yield accrual, band check)"
```

---

### Task 4: `core/ledger.py` — state persistence

**Files:**
- Create: `core/ledger.py`
- Test: `tests/test_ledger.py`

**Interfaces:**
- Produces: `DEFAULT_STATE` (dict), `load_state(path: str) -> dict`, `save_state(path: str, state: dict) -> None`, `apply_fill(contracts_held: int, delta_contracts: int, contract_year: int, contract_month: int) -> dict` returning `{"contracts_held": int, "contract_year": int, "contract_month": int}`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_ledger.py`:

```python
import json
import os

from core import ledger


def test_load_state_returns_default_when_file_missing(tmp_path):
    path = os.path.join(tmp_path, "state.json")
    state = ledger.load_state(path)
    assert state == ledger.DEFAULT_STATE


def test_save_then_load_roundtrips(tmp_path):
    path = os.path.join(tmp_path, "state.json")
    custom_state = {
        "contracts_held": 15,
        "contract_year": 2026,
        "contract_month": 9,
        "equity": 201527.4,
        "last_price": 20050.0,
        "last_run_date": "2026-07-31",
    }

    ledger.save_state(path, custom_state)
    loaded = ledger.load_state(path)

    assert loaded == custom_state
    with open(path) as f:
        assert json.load(f) == custom_state


def test_apply_fill_adds_delta_and_sets_contract_month():
    result = ledger.apply_fill(contracts_held=10, delta_contracts=5, contract_year=2026, contract_month=12)
    assert result == {"contracts_held": 15, "contract_year": 2026, "contract_month": 12}


def test_apply_fill_handles_negative_delta_flattening_to_zero():
    result = ledger.apply_fill(contracts_held=15, delta_contracts=-15, contract_year=2026, contract_month=9)
    assert result == {"contracts_held": 0, "contract_year": 2026, "contract_month": 9}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ledger.py -v`
Expected: FAIL with `ModuleNotFoundError` (`core.ledger` doesn't exist yet).

- [ ] **Step 3: Implement `core/ledger.py`**

```python
import json
import os

DEFAULT_STATE = {
    "contracts_held": 0,
    "contract_year": None,
    "contract_month": None,
    "equity": 200000.0,
    "last_price": None,
    "last_run_date": None,
}


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return dict(DEFAULT_STATE)
    with open(path, "r") as f:
        return json.load(f)


def save_state(path: str, state: dict) -> None:
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def apply_fill(contracts_held: int, delta_contracts: int, contract_year: int, contract_month: int) -> dict:
    """Return the position fields after applying a fill of delta_contracts,
    now held under the given contract month."""
    return {
        "contracts_held": contracts_held + delta_contracts,
        "contract_year": contract_year,
        "contract_month": contract_month,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ledger.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/ledger.py tests/test_ledger.py
git commit -m "feat: add state.json persistence and fill-application logic"
```

---

### Task 5: `core/pricing.py` — market data fetch with retry

**Files:**
- Create: `core/pricing.py`
- Test: `tests/test_pricing.py`

**Interfaces:**
- Produces: `download_with_retry(tickers: str, period="5d", max_retries=5, backoff_seconds=15) -> pd.DataFrame`, `fetch_price_and_yield(futures_ticker="MNQ=F", yield_ticker="^IRX") -> dict` returning `{"price": float, "annual_rate_pct": float, "date": date}`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_pricing.py`:

```python
import datetime as dt

import pandas as pd
import pytest

from core import pricing


def test_download_with_retry_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}
    good_df = pd.DataFrame({"Close": [1.0, 2.0]})

    def fake_download(tickers, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            return pd.DataFrame()
        return good_df

    monkeypatch.setattr(pricing.yf, "download", fake_download)
    monkeypatch.setattr(pricing.time, "sleep", lambda seconds: None)

    result = pricing.download_with_retry("MNQ=F ^IRX", max_retries=5)

    assert calls["count"] == 3
    pd.testing.assert_frame_equal(result, good_df)


def test_download_with_retry_raises_after_max_retries(monkeypatch):
    monkeypatch.setattr(pricing.yf, "download", lambda tickers, **kwargs: pd.DataFrame())
    monkeypatch.setattr(pricing.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError):
        pricing.download_with_retry("MNQ=F ^IRX", max_retries=3)


def test_fetch_price_and_yield_extracts_latest_close_values(monkeypatch):
    idx = pd.to_datetime(["2026-07-29", "2026-07-30"])
    columns = pd.MultiIndex.from_tuples([("Close", "MNQ=F"), ("Close", "^IRX")])
    fixture = pd.DataFrame([[20000.0, 4.5], [20150.0, 4.4]], index=idx, columns=columns)
    monkeypatch.setattr(pricing, "download_with_retry", lambda tickers, **kwargs: fixture)

    result = pricing.fetch_price_and_yield()

    assert result == {"price": 20150.0, "annual_rate_pct": 4.4, "date": dt.date(2026, 7, 30)}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pricing.py -v`
Expected: FAIL with `ModuleNotFoundError` (`core.pricing` doesn't exist yet).

- [ ] **Step 3: Implement `core/pricing.py`**

```python
import time

import yfinance as yf


def download_with_retry(tickers, period="5d", max_retries=5, backoff_seconds=15):
    """Download yfinance data with exponential back-off retry.

    Returns a non-empty DataFrame or raises RuntimeError after all retries.
    """
    backoff = backoff_seconds
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            data = yf.download(tickers, period=period, progress=False, auto_adjust=False, threads=False)
            if not data.empty:
                return data
        except Exception as e:
            last_error = e

        if attempt < max_retries:
            time.sleep(backoff)
            backoff *= 2

    raise RuntimeError(
        f"[yf.download] Failed to download '{tickers}' after {max_retries} attempts: {last_error}"
    )


def fetch_price_and_yield(futures_ticker="MNQ=F", yield_ticker="^IRX"):
    data = download_with_retry(f"{futures_ticker} {yield_ticker}")

    futures_close = data.xs(futures_ticker, axis=1, level=1)["Close"].dropna()
    yield_close = data.xs(yield_ticker, axis=1, level=1)["Close"].dropna()

    return {
        "price": float(futures_close.iloc[-1]),
        "annual_rate_pct": float(yield_close.iloc[-1]),
        "date": futures_close.index[-1].date(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pricing.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/pricing.py tests/test_pricing.py
git commit -m "feat: add MNQ price and T-bill yield fetch with retry"
```

---

### Task 6: `core/signal.py` — trade_bot signal integration

**Files:**
- Create: `core/signal.py`
- Create: `tests/fixtures/fake_trade_bot/backtest/__init__.py` (empty)
- Create: `tests/fixtures/fake_trade_bot/backtest/strat_backtest.py`
- Test: `tests/test_signal.py`

**Interfaces:**
- Produces: `leverage_from_action(action: str, target_leverage_when_buy: float = 3.0) -> float`, `fetch_signal(trade_bot_path: str, ticker: str = "SPY") -> dict` (returns whatever `SMATrendFollowing.get_live_stats` returns, which must include an `"action"` key).

- [ ] **Step 1: Write failing tests and fixtures**

Create `tests/fixtures/fake_trade_bot/backtest/__init__.py` (empty file).

Create `tests/fixtures/fake_trade_bot/backtest/strat_backtest.py`:

```python
class SMATrendFollowing:
    def __init__(self, sma_window=200, t2_confirmation=False):
        self.sma_window = sma_window
        self.t2_confirmation = t2_confirmation

    def get_live_stats(self, monitor_ticker="QQQ", leveraged_ticker="TQQQ", data=None):
        return {"action": "BUY/HOLD", "trend": "BULLISH", "qqq_price": 123.45}
```

Create `tests/test_signal.py`:

```python
import os

from core import signal


def test_leverage_from_action_buy_returns_target():
    assert signal.leverage_from_action("BUY/HOLD", 3.0) == 3.0


def test_leverage_from_action_sell_returns_zero():
    assert signal.leverage_from_action("SELL/CASH", 3.0) == 0.0


def test_fetch_signal_imports_and_calls_trade_bot_strategy():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "fake_trade_bot")

    result = signal.fetch_signal(fixture_path, ticker="SPY")

    assert result["action"] == "BUY/HOLD"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_signal.py -v`
Expected: FAIL with `ModuleNotFoundError` (`core.signal` doesn't exist yet).

- [ ] **Step 3: Implement `core/signal.py`**

```python
import sys


def leverage_from_action(action: str, target_leverage_when_buy: float = 3.0) -> float:
    return target_leverage_when_buy if action.startswith("BUY") else 0.0


def fetch_signal(trade_bot_path: str, ticker: str = "SPY") -> dict:
    """Import trade_bot's SMATrendFollowing from trade_bot_path and return its
    live stats for `ticker` (default SPY, matching trade_bot's own primary/
    RECOMMENDED ACTION signal). Re-imports fresh each call so this works whether
    trade_bot_path points at the real repo or a test fixture."""
    sys.modules.pop("backtest.strat_backtest", None)
    sys.modules.pop("backtest", None)
    if trade_bot_path not in sys.path:
        sys.path.insert(0, trade_bot_path)

    from backtest.strat_backtest import SMATrendFollowing

    strat = SMATrendFollowing(sma_window=200, t2_confirmation=True)
    return strat.get_live_stats(monitor_ticker=ticker, leveraged_ticker=ticker)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_signal.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/signal.py tests/test_signal.py tests/fixtures
git commit -m "feat: add trade_bot signal integration (leverage_from_action, fetch_signal)"
```

---

### Task 7: `bot.py` — daily context builder

**Files:**
- Create: `bot.py`
- Test: `tests/test_bot_context.py`

**Interfaces:**
- Consumes: `core.contracts.MNQ_POINT_VALUE`, `core.contracts.current_contract_month`, `core.contracts.roll_status`; `core.rebalance.update_equity`, `compute_notional_exposure`, `compute_current_leverage`, `compute_target_contracts`, `should_rebalance`, `margin_warning`; `core.ledger.apply_fill`; `core.signal.leverage_from_action`.
- Produces: module-level constants `BAND=0.2`, `TARGET_LEVERAGE_WHEN_BUY=3.0`, `ROLL_OFFSET_TRADING_DAYS=5`, `MARGIN_APPROX_RATE=0.10`, `MARGIN_WARNING_THRESHOLD=0.5`; `build_context(state: dict, price_info: dict, signal_stats: dict, today: date) -> dict` with keys `today, price, equity, contracts_held, notional, current_leverage, target_leverage, action, rebalance_needed, delta_contracts, target_contracts, roll, margin_flag, new_state`. `new_state` has keys `contracts_held, contract_year, contract_month, equity, last_price, last_run_date`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_bot_context.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_bot_context.py -v`
Expected: FAIL with `ModuleNotFoundError` (`bot` module doesn't exist yet).

- [ ] **Step 3: Implement `bot.py` (build_context only for now)**

```python
"""Daily orchestrator for the synthetic 3x QQQ futures tracker."""
import datetime as dt

from core import contracts, ledger, rebalance
from core import signal as signal_mod

BAND = 0.2
TARGET_LEVERAGE_WHEN_BUY = 3.0
ROLL_OFFSET_TRADING_DAYS = 5
MARGIN_APPROX_RATE = 0.10
MARGIN_WARNING_THRESHOLD = 0.5


def build_context(state, price_info, signal_stats, today):
    point_value = contracts.MNQ_POINT_VALUE
    price = price_info["price"]
    annual_rate_pct = price_info["annual_rate_pct"]

    equity = state["equity"]
    prior_contracts_held = state["contracts_held"]
    prior_price = state["last_price"]
    last_run_date = state["last_run_date"]

    if prior_price is not None and last_run_date is not None:
        last_run = dt.date.fromisoformat(last_run_date)
        calendar_days = (today - last_run).days
        equity = rebalance.update_equity(
            equity, prior_contracts_held, point_value, prior_price, price,
            annual_rate_pct, calendar_days,
        )

    notional = rebalance.compute_notional_exposure(prior_contracts_held, point_value, price)
    current_leverage = rebalance.compute_current_leverage(notional, equity)

    action = signal_stats["action"]
    target_leverage = signal_mod.leverage_from_action(action, TARGET_LEVERAGE_WHEN_BUY)

    rebalance_needed = rebalance.should_rebalance(current_leverage, target_leverage, BAND)
    if rebalance_needed:
        target_contracts = rebalance.compute_target_contracts(target_leverage, equity, point_value, price)
    else:
        target_contracts = prior_contracts_held
    delta_contracts = target_contracts - prior_contracts_held if rebalance_needed else 0

    contract_year = state["contract_year"]
    contract_month = state["contract_month"]
    if contract_year is None or contract_month is None:
        contract_year, contract_month = contracts.current_contract_month(today)
    roll = contracts.roll_status(today, contract_year, contract_month, ROLL_OFFSET_TRADING_DAYS)

    final_contracts_held = prior_contracts_held + delta_contracts
    final_contract_year, final_contract_month = contract_year, contract_month
    if roll["should_roll"] and final_contracts_held != 0:
        final_contract_year, final_contract_month = roll["next_year"], roll["next_month"]

    position = ledger.apply_fill(prior_contracts_held, delta_contracts, final_contract_year, final_contract_month)

    projected_notional = rebalance.compute_notional_exposure(position["contracts_held"], point_value, price)
    margin_flag = rebalance.margin_warning(projected_notional, equity, MARGIN_APPROX_RATE, MARGIN_WARNING_THRESHOLD)

    new_state = {
        "contracts_held": position["contracts_held"],
        "contract_year": position["contract_year"],
        "contract_month": position["contract_month"],
        "equity": equity,
        "last_price": price,
        "last_run_date": today.isoformat(),
    }

    return {
        "today": today,
        "price": price,
        "equity": equity,
        "contracts_held": prior_contracts_held,
        "notional": notional,
        "current_leverage": current_leverage,
        "target_leverage": target_leverage,
        "action": action,
        "rebalance_needed": rebalance_needed,
        "delta_contracts": delta_contracts,
        "target_contracts": target_contracts,
        "roll": roll,
        "margin_flag": margin_flag,
        "new_state": new_state,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_bot_context.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot_context.py
git commit -m "feat: add bot.py daily context builder (equity update, band check, roll check)"
```

---

### Task 8: `bot.py` — Discord message formatter

**Files:**
- Modify: `bot.py` (append `format_discord_message`)
- Test: `tests/test_bot_message.py`

**Interfaces:**
- Consumes: the context dict shape produced by `build_context` (Task 7).
- Produces: `format_discord_message(ctx: dict) -> str`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_bot_message.py`:

```python
import datetime as dt

import bot


def test_format_discord_message_hold_no_roll_no_margin():
    ctx = {
        "today": dt.date(2026, 7, 31),
        "price": 20050.0,
        "equity": 201527.40,
        "current_leverage": 2.98,
        "target_leverage": 3.0,
        "action": "BUY/HOLD",
        "rebalance_needed": False,
        "delta_contracts": 0,
        "target_contracts": 15,
        "roll": {
            "should_roll": False, "current_symbol": "MNQU26", "next_symbol": "MNQZ26",
            "trading_days_left": 30, "expiry": dt.date(2026, 9, 18),
            "next_year": 2026, "next_month": 12,
        },
        "margin_flag": False,
    }

    message = bot.format_discord_message(ctx)

    expected = (
        "📅 **Synthetic 3x QQQ Monitor (2026-07-31)**\n"
        "--------------------------\n"
        "• Signal: **BUY/HOLD**\n"
        "• Price (MNQ): 20050.00\n"
        "• Equity: $201527.40\n"
        "• Current Leverage: 2.98x | Target: 3.0x\n"
        "🚩 **ACTION: HOLD** — No trade — within 0.2x band"
    )
    assert message == expected


def test_format_discord_message_rebalance_with_roll_and_margin_warning():
    ctx = {
        "today": dt.date(2026, 9, 11),
        "price": 20000.0,
        "equity": 200000.0,
        "current_leverage": 2.0,
        "target_leverage": 3.0,
        "action": "BUY/HOLD",
        "rebalance_needed": True,
        "delta_contracts": 5,
        "target_contracts": 15,
        "roll": {
            "should_roll": True, "current_symbol": "MNQU26", "next_symbol": "MNQZ26",
            "trading_days_left": 5, "expiry": dt.date(2026, 9, 18),
            "next_year": 2026, "next_month": 12,
        },
        "margin_flag": True,
    }

    message = bot.format_discord_message(ctx)

    expected = (
        "📅 **Synthetic 3x QQQ Monitor (2026-09-11)**\n"
        "--------------------------\n"
        "• Signal: **BUY/HOLD**\n"
        "• Price (MNQ): 20000.00\n"
        "• Equity: $200000.00\n"
        "• Current Leverage: 2.00x | Target: 3.0x\n"
        "🚩 **ACTION: REBALANCE** — BUY 5 MNQ contract(s) -> target 15\n"
        "⚠️ Roll MNQU26 → MNQZ26 (5 trading days left)\n"
        "🔺 **Margin usage warning:** projected exposure exceeds the configured safety threshold."
    )
    assert message == expected


def test_format_discord_message_sell_side_trade_line():
    ctx = {
        "today": dt.date(2026, 8, 1), "price": 20050.0, "equity": 200000.0,
        "current_leverage": 3.0075, "target_leverage": 0.0, "action": "SELL/CASH",
        "rebalance_needed": True, "delta_contracts": -15, "target_contracts": 0,
        "roll": {
            "should_roll": False, "current_symbol": "MNQU26", "next_symbol": "MNQZ26",
            "trading_days_left": 33, "expiry": dt.date(2026, 9, 18),
            "next_year": 2026, "next_month": 12,
        },
        "margin_flag": False,
    }

    message = bot.format_discord_message(ctx)

    assert "🚩 **ACTION: REBALANCE** — SELL 15 MNQ contract(s) -> target 0" in message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_bot_message.py -v`
Expected: FAIL with `AttributeError` (`bot.format_discord_message` doesn't exist yet).

- [ ] **Step 3: Append `format_discord_message` to `bot.py`**

Add this function to `bot.py`, after `build_context`:

```python
def format_discord_message(ctx: dict) -> str:
    today_str = ctx["today"].strftime("%Y-%m-%d")
    action_line = "REBALANCE" if ctx["rebalance_needed"] else "HOLD"

    if ctx["rebalance_needed"]:
        side = "BUY" if ctx["delta_contracts"] > 0 else "SELL"
        trade_line = f"{side} {abs(ctx['delta_contracts'])} MNQ contract(s) -> target {ctx['target_contracts']}"
    else:
        trade_line = "No trade — within 0.2x band"

    lines = [
        f"📅 **Synthetic 3x QQQ Monitor ({today_str})**",
        "--------------------------",
        f"• Signal: **{ctx['action']}**",
        f"• Price (MNQ): {ctx['price']:.2f}",
        f"• Equity: ${ctx['equity']:.2f}",
        f"• Current Leverage: {ctx['current_leverage']:.2f}x | Target: {ctx['target_leverage']:.1f}x",
        f"🚩 **ACTION: {action_line}** — {trade_line}",
    ]

    if ctx["roll"]["should_roll"]:
        lines.append(
            f"⚠️ Roll {ctx['roll']['current_symbol']} → {ctx['roll']['next_symbol']} "
            f"({ctx['roll']['trading_days_left']} trading days left)"
        )

    if ctx["margin_flag"]:
        lines.append("🔺 **Margin usage warning:** projected exposure exceeds the configured safety threshold.")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_bot_message.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot_message.py
git commit -m "feat: add Discord message formatter for daily rebalance/roll status"
```

---

### Task 9: `bot.py` orchestration, CI workflow, README, initial state

**Files:**
- Modify: `bot.py` (append `run_bot()` and CLI entrypoint)
- Create: `state.json`
- Create: `.github/workflows/daily_check.yaml`
- Create: `README.md`
- Test: `tests/test_bot_run.py`

**Interfaces:**
- Consumes: `core.pricing.fetch_price_and_yield`, `core.signal.fetch_signal`, `core.ledger.load_state`/`save_state`, `bot.build_context`, `bot.format_discord_message`.
- Produces: `bot.run_bot()` — the full daily entrypoint, and `bot.STATE_PATH` / `bot.TRADE_BOT_PATH` module constants.

- [ ] **Step 1: Write failing wiring test**

Create `tests/test_bot_run.py`:

```python
import datetime as dt

import bot
from core import ledger, pricing
from core import signal as signal_mod


def test_run_bot_wires_components_and_prints_when_no_webhook(monkeypatch, tmp_path, capsys):
    state_path = str(tmp_path / "state.json")
    monkeypatch.setattr(bot, "STATE_PATH", state_path)
    monkeypatch.setattr(ledger, "load_state", lambda path: dict(ledger.DEFAULT_STATE))
    monkeypatch.setattr(
        pricing, "fetch_price_and_yield",
        lambda: {"price": 20000.0, "annual_rate_pct": 5.0, "date": dt.date(2026, 7, 30)},
    )
    monkeypatch.setattr(
        signal_mod, "fetch_signal",
        lambda trade_bot_path, ticker="SPY": {"action": "BUY/HOLD"},
    )
    saved = {}
    monkeypatch.setattr(ledger, "save_state", lambda path, state: saved.update(state))
    monkeypatch.delenv("DISCORD_WEBHOOK", raising=False)

    bot.run_bot()

    captured = capsys.readouterr()
    assert "Synthetic 3x QQQ Monitor" in captured.out
    assert saved["contracts_held"] == 15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bot_run.py -v`
Expected: FAIL with `AttributeError` (`bot.run_bot` doesn't exist yet).

- [ ] **Step 3: Append `run_bot()` and imports to `bot.py`**

Add these imports to the top of `bot.py` (alongside the existing ones):

```python
import os

import requests

from core import pricing
```

Add this after `format_discord_message`, and add the `if __name__ == "__main__":` block at the very end of the file:

```python
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "state.json")
TRADE_BOT_PATH = os.environ.get("TRADE_BOT_PATH", os.path.join(HERE, "trade_bot"))


def run_bot():
    state = ledger.load_state(STATE_PATH)
    price_info = pricing.fetch_price_and_yield()
    signal_stats = signal_mod.fetch_signal(TRADE_BOT_PATH)

    ctx = build_context(state, price_info, signal_stats, price_info["date"])
    message = format_discord_message(ctx)

    webhook_url = os.environ.get("DISCORD_WEBHOOK")
    if webhook_url:
        requests.post(webhook_url, json={"content": message})
    else:
        print(message)

    ledger.save_state(STATE_PATH, ctx["new_state"])


if __name__ == "__main__":
    run_bot()
```

(Note: `STATE_PATH` and `TRADE_BOT_PATH` must be defined as plain module-level globals, not inside a function, so that `monkeypatch.setattr(bot, "STATE_PATH", ...)` in the test above can override them before `run_bot()` reads them.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bot_run.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Create initial `state.json`**

```json
{
  "contracts_held": 0,
  "contract_year": null,
  "contract_month": null,
  "equity": 200000.0,
  "last_price": null,
  "last_run_date": null
}
```

- [ ] **Step 6: Create `.github/workflows/daily_check.yaml`**

```yaml
name: Synthetic 3x QQQ Monitor

on:
  schedule:
    - cron: '35 0 * * 1-5'
  workflow_dispatch:

jobs:
  run-bot:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout synthetic_tqqq
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Checkout trade_bot (signal source)
        uses: actions/checkout@v4
        with:
          repository: jerry0815/trade_bot
          path: trade_bot

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run Bot
        run: python bot.py
        env:
          DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK }}

      - name: Commit updated state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add state.json
          git diff --quiet --cached || git commit -m "chore: update state.json after daily run"
          git push
```

- [ ] **Step 7: Create `README.md`**

```markdown
# synthetic_tqqq

Tracks a synthetic 3x-leveraged QQQ position held via MNQ (Micro E-mini
Nasdaq-100) futures instead of buying TQQQ shares, using band rebalancing
(only trade when leverage drifts more than 0.2x from target) instead of
TQQQ's continuous daily reset. A Discord bot notifies the recommended daily
action — this project never places trades automatically.

Full design: [docs/superpowers/specs/2026-07-31-synthetic-tqqq-design.md](docs/superpowers/specs/2026-07-31-synthetic-tqqq-design.md)

## How it works

Each trading day, `bot.py`:
1. Reads trade_bot's SMA200+ATR S&P 500 signal to decide the target leverage (3.0x if BUY, 0.0x if SELL).
2. Fetches MNQ futures price and the current T-bill yield.
3. Updates tracked equity (prior equity + mark-to-market P&L on held contracts + accrued T-bill yield on idle capital).
4. Compares current leverage to target; if drift exceeds 0.2x, recommends a BUY/SELL of N contracts.
5. Flags an upcoming contract roll if within 5 trading days of quarterly expiry.
6. Posts the combined status to Discord (or prints it locally if `DISCORD_WEBHOOK` isn't set).
7. Commits the updated `state.json` ledger.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. This project depends on [trade_bot](https://github.com/jerry0815/trade_bot) for its trend signal.
   - **Locally:** clone trade_bot as a sibling directory and set `TRADE_BOT_PATH`, e.g. (PowerShell):
     ```powershell
     $env:TRADE_BOT_PATH = "C:\jerry\toy_work\trade_bot"
     ```
   - **In GitHub Actions:** already handled — the workflow checks trade_bot out into `./trade_bot`.
3. Add a `DISCORD_WEBHOOK` repository secret (Settings > Secrets and variables > Actions) for live notifications. Without it, `bot.py` just prints the message.
4. The workflow at `.github/workflows/daily_check.yaml` runs automatically on trading days after market close (needs `permissions: contents: write`, already configured, to commit `state.json` back).

## Comparing against TQQQ

`python -m compare.backtest_vs_tqqq` simulates this strategy back to TQQQ's
2010-02-11 inception using NQ=F futures history, and writes a comparison
table to `compare/output.md`. See Section 8 of the design doc for details.

## Risk disclaimer

This is an educational/monitoring tool, not an execution system — no trades
are auto-placed. Futures leverage carries margin-call risk that
daily-checked band rebalancing does not fully protect against (a large
intraday move between runs could breach margin before the next check). The
T-bill-yield and financing-cost assumptions in the backtest are
approximations, not guarantees of live tracking accuracy. Assess your own
risk tolerance before executing real-world trades based on these
recommendations.
```

- [ ] **Step 8: Commit**

```bash
git add bot.py state.json .github/workflows/daily_check.yaml README.md tests/test_bot_run.py
git commit -m "feat: wire up bot.py orchestration, CI workflow, initial state, and README"
```

---

### Task 10: `compare/backtest_vs_tqqq.py` — historical simulation

**Files:**
- Create: `compare/backtest_vs_tqqq.py`
- Test: `tests/test_backtest_simulate.py`

**Interfaces:**
- Consumes: `core.rebalance.update_equity`, `compute_notional_exposure`, `compute_current_leverage`, `should_rebalance`, `compute_target_contracts`.
- Produces: `simulate(prices: pd.Series, in_market: pd.Series, tbill_rates: pd.Series, initial_equity=200000.0, point_value=2.0, target_leverage_when_in=3.0, band=0.2) -> pd.DataFrame` indexed the same as the inputs, with columns `equity, contracts_held, notional, current_leverage, target_leverage, rebalanced`. All three input series must share the same `DatetimeIndex`, already aligned by the caller.

- [ ] **Step 1: Write failing test**

Create `tests/test_backtest_simulate.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backtest_simulate.py -v`
Expected: FAIL with `ModuleNotFoundError` (`compare.backtest_vs_tqqq` doesn't exist yet).

- [ ] **Step 3: Implement `simulate()` in `compare/backtest_vs_tqqq.py`**

```python
"""One-off report: compares this project's band-rebalanced synthetic 3x QQQ
(via NQ futures) against actually holding TQQQ, since TQQQ's 2010-02-11
inception. Not part of the daily bot — run manually with
`python -m compare.backtest_vs_tqqq`."""
import pandas as pd

from core import rebalance

POINT_VALUE = 2.0
TQQQ_INCEPTION = "2010-02-11"


def simulate(
    prices: pd.Series,
    in_market: pd.Series,
    tbill_rates: pd.Series,
    initial_equity: float = 200000.0,
    point_value: float = POINT_VALUE,
    target_leverage_when_in: float = 3.0,
    band: float = 0.2,
) -> pd.DataFrame:
    equity = initial_equity
    contracts_held = 0
    prior_price = None
    prior_date = None
    rows = []

    for date in prices.index:
        price = float(prices.loc[date])
        rate = float(tbill_rates.loc[date])

        if prior_price is not None:
            calendar_days = (date - prior_date).days
            equity = rebalance.update_equity(
                equity, contracts_held, point_value, prior_price, price, rate, calendar_days,
            )

        target_leverage = target_leverage_when_in if bool(in_market.loc[date]) else 0.0
        notional = rebalance.compute_notional_exposure(contracts_held, point_value, price)
        current_leverage = rebalance.compute_current_leverage(notional, equity)
        rebalanced = rebalance.should_rebalance(current_leverage, target_leverage, band)

        if rebalanced:
            contracts_held = rebalance.compute_target_contracts(target_leverage, equity, point_value, price)
            notional = rebalance.compute_notional_exposure(contracts_held, point_value, price)
            current_leverage = rebalance.compute_current_leverage(notional, equity)

        rows.append({
            "date": date,
            "equity": equity,
            "contracts_held": contracts_held,
            "notional": notional,
            "current_leverage": current_leverage,
            "target_leverage": target_leverage,
            "rebalanced": rebalanced,
        })

        prior_price = price
        prior_date = date

    return pd.DataFrame(rows).set_index("date")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_backtest_simulate.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add compare/backtest_vs_tqqq.py tests/test_backtest_simulate.py
git commit -m "feat: add historical band-rebalance simulation for delta-vs-TQQQ backtest"
```

---

### Task 11: `compare/backtest_vs_tqqq.py` — performance metrics

**Files:**
- Modify: `compare/backtest_vs_tqqq.py` (append `compute_metrics`)
- Test: `tests/test_backtest_metrics.py`

**Interfaces:**
- Consumes: an `equity`-like `pd.Series` indexed by date (works identically for the synthetic equity curve from `simulate()` or a raw TQQQ close-price series).
- Produces: `compute_metrics(equity: pd.Series) -> dict` with keys `total_return, cagr, max_drawdown` (all as decimals, e.g. `0.21` for 21%).

- [ ] **Step 1: Write failing tests**

Create `tests/test_backtest_metrics.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_backtest_metrics.py -v`
Expected: FAIL with `ImportError` (`compute_metrics` doesn't exist yet).

- [ ] **Step 3: Append `compute_metrics` to `compare/backtest_vs_tqqq.py`**

```python
def compute_metrics(equity: pd.Series) -> dict:
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    max_drawdown = drawdown.min()
    return {"total_return": total_return, "cagr": cagr, "max_drawdown": max_drawdown}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_backtest_metrics.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add compare/backtest_vs_tqqq.py tests/test_backtest_metrics.py
git commit -m "feat: add CAGR/max-drawdown/total-return metrics for backtest comparison"
```

---

### Task 12: `compare/backtest_vs_tqqq.py` — report generation and live data wiring

**Files:**
- Modify: `compare/backtest_vs_tqqq.py` (append `generate_report` and `main`)
- Test: `tests/test_backtest_report.py`

**Interfaces:**
- Consumes: two `dict`s from `compute_metrics` (Task 11) — one for the synthetic strategy, one for TQQQ.
- Produces: `generate_report(synthetic_metrics: dict, tqqq_metrics: dict) -> str` (markdown table), `main() -> None` (downloads real data, runs the full pipeline, writes `compare/output.md`).

- [ ] **Step 1: Write failing test**

Create `tests/test_backtest_report.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backtest_report.py -v`
Expected: FAIL with `ImportError` (`generate_report` doesn't exist yet).

- [ ] **Step 3: Append `generate_report` and `main` to `compare/backtest_vs_tqqq.py`**

```python
def generate_report(synthetic_metrics: dict, tqqq_metrics: dict) -> str:
    delta_cagr = synthetic_metrics["cagr"] - tqqq_metrics["cagr"]
    lines = [
        "| Metric | Synthetic (Futures + Band Rebalance) | Actual TQQQ |",
        "| --- | ---: | ---: |",
        f"| CAGR | {synthetic_metrics['cagr']*100:.2f}% | {tqqq_metrics['cagr']*100:.2f}% |",
        f"| Max Drawdown | {synthetic_metrics['max_drawdown']*100:.2f}% | {tqqq_metrics['max_drawdown']*100:.2f}% |",
        f"| Total Return | {synthetic_metrics['total_return']*100:.2f}% | {tqqq_metrics['total_return']*100:.2f}% |",
        f"| Annualized Delta (synthetic - TQQQ) | {delta_cagr*100:+.2f}% | |",
    ]
    return "\n".join(lines)


def main():
    import os
    import sys

    import yfinance as yf

    trade_bot_path = os.environ.get(
        "TRADE_BOT_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "trade_bot"),
    )
    if trade_bot_path not in sys.path:
        sys.path.insert(0, trade_bot_path)
    from backtest.strat_backtest import SMATrendFollowing, get_cached_signals

    gspc = get_cached_signals("^GSPC", sma_window=200)
    strat = SMATrendFollowing(sma_window=200, t2_confirmation=True)
    gspc, _ = strat.generate_signals(gspc)

    nq = yf.download("NQ=F", start=TQQQ_INCEPTION, progress=False, auto_adjust=False)
    tqqq = yf.download("TQQQ", start=TQQQ_INCEPTION, progress=False, auto_adjust=False)
    irx = yf.download("^IRX", start=TQQQ_INCEPTION, progress=False, auto_adjust=False)
    for df in (nq, tqqq, irx):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

    common_index = gspc.index.intersection(nq.index).intersection(irx.index)
    common_index = common_index[common_index >= pd.Timestamp(TQQQ_INCEPTION)]

    prices = nq["Close"].reindex(common_index).ffill()
    in_market = gspc["in_market"].reindex(common_index).ffill()
    tbill = irx["Close"].reindex(common_index).ffill()

    result = simulate(prices, in_market, tbill, initial_equity=200000.0)
    synthetic_metrics = compute_metrics(result["equity"])

    tqqq_close = tqqq["Close"].reindex(common_index).ffill()
    tqqq_metrics = compute_metrics(tqqq_close)

    report = generate_report(synthetic_metrics, tqqq_metrics)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.md")
    with open(out_path, "w") as f:
        f.write(report + "\n")

    print(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_backtest_report.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Manually verify `main()` against live data**

`main()` is network-dependent (yfinance + trade_bot's cached signal download) and isn't covered by an automated test — same as trade_bot's own backtest scripts. Verify it by hand:

Run (from `synthetic_tqqq/`, with `TRADE_BOT_PATH` set per the README):
```bash
python -m compare.backtest_vs_tqqq
```
Expected: prints a markdown comparison table to stdout and writes it to `compare/output.md`. Sanity-check the numbers look plausible (synthetic CAGR should be in the same ballpark as TQQQ's, not off by orders of magnitude — if it is, check the `common_index` alignment and `ffill()` calls first).

- [ ] **Step 6: Commit**

```bash
git add compare/backtest_vs_tqqq.py tests/test_backtest_report.py compare/output.md
git commit -m "feat: add comparison report generation and live backtest wiring"
```

---

## Self-Review

**Spec coverage:** Section 3 (structure) → Task 1. Section 4 (rebalance math, corrected to a single running-equity model — see note at the top of this plan) → Tasks 3, 7. Section 5 (signal integration) → Task 6. Section 6 (roll handling) → Tasks 2, 7. Section 7 (daily bot flow) → Tasks 7-9. Section 8 (backtest) → Tasks 10-12. Section 9 (testing) → every task is TDD'd. Section 10 (error handling) → Task 5's retry logic; Task 9's `run_bot` doesn't currently special-case a signal-fetch failure into a "signal unavailable" message as the spec's Section 10 describes — **gap found and fixed below.**

**Fix applied:** Task 9's `run_bot()` did not wrap `signal_mod.fetch_signal(...)` to degrade gracefully on failure, contradicting spec Section 10 ("if trade_bot's signal fetch fails outright, the bot still posts a Discord message... flags signal unavailable"). Revise Task 9 Step 3's `run_bot()` to:

```python
def run_bot():
    state = ledger.load_state(STATE_PATH)
    price_info = pricing.fetch_price_and_yield()

    try:
        signal_stats = signal_mod.fetch_signal(TRADE_BOT_PATH)
        signal_error = None
    except Exception as e:
        signal_stats = {"action": "SELL/CASH"}
        signal_error = str(e)

    ctx = build_context(state, price_info, signal_stats, price_info["date"])
    message = format_discord_message(ctx)
    if signal_error:
        message += f"\n⚠️ **Signal unavailable — defaulted to defensive.** ({signal_error})"

    webhook_url = os.environ.get("DISCORD_WEBHOOK")
    if webhook_url:
        requests.post(webhook_url, json={"content": message})
    else:
        print(message)

    ledger.save_state(STATE_PATH, ctx["new_state"])
```

This defaults to `SELL/CASH` (target_leverage 0.0) on signal failure — safer than guessing BUY — and clearly flags the degraded state in the message rather than silently recommending a trade based on a fabricated signal. Task 9's wiring test (`test_run_bot_wires_components_and_prints_when_no_webhook`) still passes unchanged since it mocks `fetch_signal` to succeed; no test currently covers the failure branch, so add one more test to Task 9's `tests/test_bot_run.py`:

```python
def test_run_bot_defaults_to_defensive_when_signal_fetch_fails(monkeypatch, tmp_path, capsys):
    state_path = str(tmp_path / "state.json")
    monkeypatch.setattr(bot, "STATE_PATH", state_path)
    monkeypatch.setattr(ledger, "load_state", lambda path: dict(ledger.DEFAULT_STATE))
    monkeypatch.setattr(
        pricing, "fetch_price_and_yield",
        lambda: {"price": 20000.0, "annual_rate_pct": 5.0, "date": dt.date(2026, 7, 30)},
    )

    def raise_error(trade_bot_path, ticker="SPY"):
        raise RuntimeError("yfinance rate-limited")

    monkeypatch.setattr(signal_mod, "fetch_signal", raise_error)
    saved = {}
    monkeypatch.setattr(ledger, "save_state", lambda path, state: saved.update(state))
    monkeypatch.delenv("DISCORD_WEBHOOK", raising=False)

    bot.run_bot()

    captured = capsys.readouterr()
    assert "Signal unavailable — defaulted to defensive" in captured.out
    assert saved["contracts_held"] == 0
```

Amend Task 9's Step 1 to include this test alongside the original, and Step 3/4 to use the revised `run_bot()` above.

**Placeholder scan:** No `TBD`/`TODO` in any task. All steps show full runnable code, no "similar to Task N" shortcuts.

**Type consistency:** `contracts_held` is `int` everywhere (from `round()` in `compute_target_contracts` and `ledger.apply_fill`'s integer arithmetic). `state` dict keys (`contracts_held, contract_year, contract_month, equity, last_price, last_run_date`) are identical across `ledger.DEFAULT_STATE`, `build_context`'s `new_state`, and every test fixture. `ctx` dict keys are identical between `build_context`'s return and `format_discord_message`'s usage. `roll` dict keys (`expiry, trading_days_left, should_roll, current_symbol, next_symbol, next_year, next_month`) match between `contracts.roll_status` and every consumer (`build_context`, `format_discord_message`, tests).

