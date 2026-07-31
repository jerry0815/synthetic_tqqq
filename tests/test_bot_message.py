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
