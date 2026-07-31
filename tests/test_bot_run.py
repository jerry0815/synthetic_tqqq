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
