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
