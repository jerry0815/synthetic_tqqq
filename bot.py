"""Daily orchestrator for the synthetic 3x QQQ futures tracker."""
import datetime as dt
import os

import requests

from core import contracts, ledger, pricing, rebalance
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


HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "state.json")
TRADE_BOT_PATH = os.environ.get("TRADE_BOT_PATH", os.path.join(HERE, "trade_bot"))


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


if __name__ == "__main__":
    run_bot()
