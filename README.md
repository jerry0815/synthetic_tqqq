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
2. This project depends on [trade_bot](https://github.com/jerry0815/trade_bot) for its trend signal, included as a git submodule at `./trade_bot`.
   - **Cloning fresh:** `git clone --recurse-submodules <this-repo-url>`
   - **Already cloned:** `git submodule update --init`
   - `bot.py` and `compare/backtest_vs_tqqq.py` default to `./trade_bot` automatically — no path configuration needed, locally or in CI. Set `TRADE_BOT_PATH` only to override this (e.g. to point at a separate local trade_bot checkout instead of the pinned submodule commit).
   - The submodule pins a specific trade_bot commit. To pick up upstream trade_bot changes: `git submodule update --remote trade_bot`, then commit the updated pointer.
3. Add a `DISCORD_WEBHOOK` repository secret (Settings > Secrets and variables > Actions) for live notifications. Without it, `bot.py` just prints the message.
4. The workflow at `.github/workflows/daily_check.yaml` runs automatically on trading days after market close (needs `permissions: contents: write`, already configured, to commit `state.json` back; checks out submodules automatically).

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
