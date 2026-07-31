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
