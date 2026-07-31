import datetime as dt

import pandas as pd
import pytest

from core import pricing


def test_download_with_retry_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}
    good_df = pd.DataFrame({"Close": [1.0, 2.0]})

    def fake_download(tickers, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            return pd.DataFrame()
        return good_df

    monkeypatch.setattr(pricing.yf, "download", fake_download)
    monkeypatch.setattr(pricing.time, "sleep", lambda seconds: None)

    result = pricing.download_with_retry("MNQ=F ^IRX", max_retries=5)

    assert calls["count"] == 3
    pd.testing.assert_frame_equal(result, good_df)


def test_download_with_retry_raises_after_max_retries(monkeypatch):
    monkeypatch.setattr(pricing.yf, "download", lambda tickers, **kwargs: pd.DataFrame())
    monkeypatch.setattr(pricing.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError):
        pricing.download_with_retry("MNQ=F ^IRX", max_retries=3)


def test_fetch_price_and_yield_extracts_latest_close_values(monkeypatch):
    idx = pd.to_datetime(["2026-07-29", "2026-07-30"])
    columns = pd.MultiIndex.from_tuples([("Close", "MNQ=F"), ("Close", "^IRX")])
    fixture = pd.DataFrame([[20000.0, 4.5], [20150.0, 4.4]], index=idx, columns=columns)
    monkeypatch.setattr(pricing, "download_with_retry", lambda tickers, **kwargs: fixture)

    result = pricing.fetch_price_and_yield()

    assert result == {"price": 20150.0, "annual_rate_pct": 4.4, "date": dt.date(2026, 7, 30)}
