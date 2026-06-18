"""Thin EODHD REST client.

Public API facts (from https://eodhd.com docs):
  - Symbol list:  GET /api/exchange-symbol-list/{EXCHANGE}
  - End-of-day:   GET /api/eod/{SYMBOL}        (SYMBOL like COMI.EGX)
  - Fundamentals: GET /api/fundamentals/{SYMBOL}
Auth via ?api_token=...  401 = bad/invalid token, 403 = plan lacks access.
The Egyptian Exchange code is "EGX" and tickers look like CODE.EGX.
"""
from __future__ import annotations

import datetime as dt

import requests

from app.config import settings

_BASE = "https://eodhd.com/api"


class EODHDError(RuntimeError):
    pass


class EODHDAuthError(EODHDError):
    """401/403 — token invalid or plan does not cover the requested data."""


class EODHDClient:
    def __init__(self, token: str | None = None, timeout: int = 60):
        self.token = token or settings.eodhd_api_token
        self.timeout = timeout
        self._session = requests.Session()

    def _get(self, path: str, **params):
        if not self.token:
            raise EODHDAuthError("EODHD_API_TOKEN is not set")
        params.update({"api_token": self.token, "fmt": "json"})
        resp = self._session.get(f"{_BASE}/{path}", params=params, timeout=self.timeout)
        if resp.status_code in (401, 403):
            raise EODHDAuthError(
                f"{resp.status_code} from EODHD ({path}): "
                + ("invalid token" if resp.status_code == 401 else "plan lacks access")
            )
        if resp.status_code != 200:
            raise EODHDError(f"{resp.status_code} from EODHD ({path}): {resp.text[:200]}")
        return resp.json()

    def symbol_list(self, exchange: str | None = None) -> list[dict]:
        exchange = exchange or settings.egx_exchange
        data = self._get(f"exchange-symbol-list/{exchange}")
        if not isinstance(data, list):
            raise EODHDError("symbol list: unexpected payload")
        return data

    def eod(self, symbol: str, start: dt.date | None = None) -> list[dict]:
        """Daily OHLCV, oldest-first. Pulls full history unless `start` given."""
        params = {"period": "d", "order": "a"}
        if start:
            params["from"] = start.isoformat()
        data = self._get(f"eod/{symbol}", **params)
        if not isinstance(data, list):
            raise EODHDError(f"eod {symbol}: unexpected payload")
        return data

    def fundamentals(self, symbol: str) -> dict:
        data = self._get(f"fundamentals/{symbol}")
        if not isinstance(data, dict):
            raise EODHDError(f"fundamentals {symbol}: unexpected payload")
        return data

    def ping(self) -> dict:
        """Quick auth/connectivity check. Returns {ok, detail}."""
        try:
            data = self.symbol_list()
            return {"ok": True, "detail": f"{len(data)} symbols on {settings.egx_exchange}"}
        except EODHDAuthError as e:
            return {"ok": False, "detail": str(e)}
        except EODHDError as e:
            return {"ok": False, "detail": str(e)}
