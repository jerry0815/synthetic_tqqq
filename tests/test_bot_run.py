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


def test_run_bot_posts_to_discord_with_timeout_when_webhook_set(monkeypatch, tmp_path):
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
    monkeypatch.setattr(ledger, "save_state", lambda path, state: None)
    monkeypatch.setenv("DISCORD_WEBHOOK", "https://discord.example/webhook")

    posted = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        posted["url"] = url
        posted["json"] = json
        posted["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(bot.requests, "post", fake_post)

    bot.run_bot()

    assert posted["url"] == "https://discord.example/webhook"
    assert "Synthetic 3x QQQ Monitor" in posted["json"]["content"]
    assert posted["timeout"] == 10


def test_run_bot_prints_error_when_discord_post_fails(monkeypatch, tmp_path, capsys):
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
    monkeypatch.setattr(ledger, "save_state", lambda path, state: None)
    monkeypatch.setenv("DISCORD_WEBHOOK", "https://discord.example/webhook")

    def fake_post(url, json, timeout):
        raise bot.requests.exceptions.RequestException("connection refused")

    monkeypatch.setattr(bot.requests, "post", fake_post)

    bot.run_bot()

    captured = capsys.readouterr()
    assert "Failed to post to Discord" in captured.out


def test_run_bot_notifies_and_skips_state_update_when_pricing_fails(monkeypatch, tmp_path, capsys):
    state_path = str(tmp_path / "state.json")
    monkeypatch.setattr(bot, "STATE_PATH", state_path)
    monkeypatch.setattr(ledger, "load_state", lambda path: dict(ledger.DEFAULT_STATE))

    def raise_error():
        raise RuntimeError("yfinance rate-limited")

    monkeypatch.setattr(pricing, "fetch_price_and_yield", raise_error)
    saved = {}
    monkeypatch.setattr(ledger, "save_state", lambda path, state: saved.update(state))
    monkeypatch.delenv("DISCORD_WEBHOOK", raising=False)

    bot.run_bot()

    captured = capsys.readouterr()
    assert "Market data unavailable" in captured.out
    assert saved == {}
