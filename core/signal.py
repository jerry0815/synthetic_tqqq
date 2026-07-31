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
