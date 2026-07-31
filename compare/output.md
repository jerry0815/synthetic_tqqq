| Metric | Synthetic (Futures + Band Rebalance) | Actual TQQQ |
| --- | ---: | ---: |
| CAGR | 25.60% | 41.19% |
| Max Drawdown | -69.39% | -81.75% |
| Total Return | 4161.81% | 29168.16% |
| # Rebalance trades | 275 | 0 |
| Annualized Delta (synthetic - TQQQ) | -15.60% | |

The synthetic strategy only holds 3x exposure while trade_bot's SMA200+ATR S&P 500 signal is bullish, sitting in cash the rest of the time; TQQQ's buy-and-hold benchmark stays fully invested throughout. That signal-gating, plus the 0.2x rebalance band's looser tracking of daily leverage versus TQQQ's continuous daily reset, is the primary driver of the delta above — traded off against a shallower max drawdown.
