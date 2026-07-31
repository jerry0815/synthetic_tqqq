# synthetic_tqqq — Design Spec

Date: 2026-07-31

## 1. Purpose

Replicate TQQQ-like 3x leveraged QQQ/Nasdaq-100 exposure by personally trading Micro E-mini
Nasdaq-100 futures (MNQ) instead of buying TQQQ shares, using a **band rebalance** approach
(only trade when actual leverage drifts more than 0.2x away from a 3.0x target) rather than
TQQQ's continuous daily reset. A Discord bot notifies the recommended rebalance/roll action
each trading day, mirroring the existing [trade_bot](../../../../trade_bot) project's
notification pattern. A separate one-off backtest compares this approach's historical
performance against actually holding TQQQ.

The long-term goal is to combine this project with trade_bot's SMA200+ATR trend signal:
trade_bot's signal decides *whether* to be invested (BUY) or defensive (SELL); this project
decides *how much futures exposure* to hold to synthesize 3x QQQ when invested, and manages
drift/rebalancing/rolling of the actual futures position over time.

## 2. Non-goals

- No automated trade execution — this is a notify-only tool, same as trade_bot. All trades are
  executed manually by the user after reading the Discord message.
- No margin-call handling or enforcement — margin usage is surfaced as an informational warning
  only, never blocks or forces an action.
- No commission/slippage modeling in the backtest (consistent with trade_bot's existing backtest,
  which also excludes ETF trading costs).

## 3. Project structure

New sibling directory to trade_bot, own git repository:

```
synthetic_tqqq/
├── core/
│   ├── contracts.py      # MNQ contract specs (point value $2), quarterly expiry calendar, roll-date window logic
│   ├── pricing.py        # yfinance fetch for MNQ=F/NQ=F price + T-bill yield (^IRX), retry logic
│   ├── signal.py         # integration with trade_bot's SMATrendFollowing to get today's BUY/SELL action
│   ├── ledger.py         # state.json load/save; applies a rebalance as a simulated fill
│   └── rebalance.py      # leverage math: equity, current leverage, band check, target contract count
├── state.json             # persisted ledger: contracts held, contract month, cash, last equity, last run date
├── bot.py                 # daily orchestrator; posts to Discord, commits state.json
├── compare/
│   └── backtest_vs_tqqq.py  # historical delta-vs-TQQQ comparison (one-off report generator)
├── tests/                 # unit tests, written test-first during implementation
├── .github/workflows/daily_check.yaml
├── requirements.txt        # yfinance, pandas, numpy, requests
└── README.md
```

## 4. Daily rebalance engine

**Contract spec:** MNQ (Micro E-mini Nasdaq-100), point value $2/point, quarterly expiry
(Mar/Jun/Sep/Dec, symbols H/M/U/Z).

**Each day's calculation (`core/rebalance.py`):**

`current_price` throughout is that trading day's closing price (the bot runs after US market
close via the same cron schedule as trade_bot), used as a same-day settlement approximation for
both the mark-to-market and any recommended trade. This is a simplification — a real fill the
next session could occur at a different price — consistent with the notify-only, no-execution
scope in Section 2.

1. `equity = cash + (contracts_held × $2 × current_price) + accrued_tbill_yield_since_last_run`
   — idle cash earns the current 13-week T-bill rate (`^IRX`), accrued daily since the last run.
2. `target_leverage = 3.0` if trade_bot's S&P 500 signal is `BUY/HOLD`, else `0.0`.
3. `notional_exposure = contracts_held × $2 × current_price`
4. `current_leverage = notional_exposure / equity`
5. **Band check:** if `abs(current_leverage - target_leverage) > 0.2` → rebalance triggers:
   - `target_contracts = round(target_leverage × equity / ($2 × current_price))`
   - `delta_contracts = target_contracts - contracts_held` → BUY/SELL N contracts recommendation.
   - If within band → HOLD, message reports current drift only, no trade recommended.
6. **Margin safety check (informational only):** if margin usage (approximated from notional
   exposure) exceeds a configurable warning threshold (default 50% of equity), the Discord
   message includes a risk warning. This never blocks or alters the recommended action.

On a rebalance or roll, `ledger.py` assumes the recommended trade filled exactly at that day's
settlement price, updates `contracts_held`/`cash`/`equity` in `state.json`, and the CI workflow
commits the updated file back to the repo.

## 5. Signal integration

`core/signal.py` calls `SMATrendFollowing(sma_window=200, t2_confirmation=True).get_live_stats("QQQ",
"TQQQ", data=...)` from trade_bot's `backtest/strat_backtest.py`, and uses
`stats_sp500['action']` — the same S&P 500-driven signal trade_bot's own `bot.py` surfaces as its
`RECOMMENDED ACTION` — as the master signal for `target_leverage`.

**Cross-repo dependency:** trade_bot is public on GitHub (`jerry0815/trade_bot`). The CI workflow
does a second `actions/checkout` step against that repo into a subfolder (no PAT required since
it's public) and `sys.path.insert()`s it before importing. Locally, the same sys.path trick
points at the sibling `../trade_bot` directory.

## 6. Roll handling

`core/contracts.py` tracks each quarter's expiry (3rd Friday of Mar/Jun/Sep/Dec) and a
configurable roll-offset (default: 5 trading days before expiry). Within that window, the
Discord message adds a reminder line (e.g. `⚠️ Roll MNQ Z25 → H26 by 2026-03-13`) alongside the
normal rebalance/hold status. This is informational only — it does not force a trade on its own;
the user executes the roll manually like any other recommended action.

## 7. Daily bot flow (`bot.py`)

1. Load `state.json`.
2. Fetch trade_bot's signal, MNQ price, and T-bill rate.
3. Compute equity, current leverage, band check, roll check.
4. Compose one combined Discord message: today's SMA trend (bullish/bearish), current leverage
   vs 3x target, recommended contract trade (if any), roll reminder (if applicable).
5. POST to the Discord webhook.
6. Update and git-commit `state.json`.

**Automation:** `.github/workflows/daily_check.yaml`, same cron schedule as trade_bot
(`30 0 * * 1-5`, after US market close), `DISCORD_WEBHOOK` secret, `contents: write` permission
to commit state back.

## 8. Delta-vs-TQQQ comparison backtest

`compare/backtest_vs_tqqq.py` simulates this exact strategy day-by-day since TQQQ's inception
(2010-02-11) using:

- **NQ=F** continuous price series as the futures proxy (longer history than MNQ, which only
  launched May 2019; contract size doesn't affect the % return simulation).
- The same SMA200+ATR T+2 S&P-signal-drives-NDX-exposure setup as trade_bot's README Table 3,
  via `get_cached_signals('^GSPC')`.
- Same $200k initial capital, 3.0x/0.0x target leverage, 0.2x band, T-bill yield on idle cash
  (reusing trade_bot's era-accurate borrow-rate table where applicable for financing cost).
- No commission/slippage modeling.

**Output:** a comparison table (mirroring trade_bot's README table style):

| Metric | Synthetic (Futures + Band Rebalance) | Actual TQQQ |
|---|---|---|
| CAGR | | |
| Max Drawdown | | |
| Total Return | | |
| # Rebalance trades | | |
| Annualized Delta (synthetic − TQQQ) | | |

Plus a short breakdown of *why* they diverge: T-bill yield earned on idle cash (edge for
synthetic), rebalance-band slippage vs TQQQ's continuous daily reset (cost for synthetic), and
financing-rate assumptions (NQ futures implied financing vs TQQQ's actual expense ratio + borrow
cost). This is a one-off report generator, not part of the daily bot.

## 9. Testing

TDD during implementation:

- Unit tests for pure-math pieces: leverage calc, band-trigger boundary conditions (exactly at
  0.2x, just inside/outside), target-contract rounding, roll-date window logic — deterministic,
  no network calls.
- `pricing.py`/`signal.py` (network-dependent) get integration tests using mocked/fixture data,
  not live yfinance calls in CI.

## 10. Error handling

Mirrors trade_bot's patterns: exponential-backoff retry on yfinance downloads. If trade_bot's
signal fetch fails outright, the bot still posts a Discord message showing current
leverage/drift but explicitly flags "signal unavailable — no rebalance recommendation today"
rather than guessing a target leverage.

## 11. Risk disclaimer (for README)

This is an educational/monitoring tool, not an execution system — no trades are auto-placed.
Futures leverage carries margin-call risk that daily-checked band rebalancing does not fully
protect against (a large intraday move between runs could breach margin before the next check).
The T-bill-yield and financing-cost assumptions in the backtest are approximations, not
guarantees of live tracking accuracy. Assess your own risk tolerance before executing real-world
trades based on these recommendations.
