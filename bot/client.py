import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("trading_bot.client")

# Binance Futures Testnet base URL
TESTNET_BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_TIMEOUT = 10


class BinanceClientError(Exception):
    """Custom exception for Binance API errors (bad response code in body)."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Binance API Error [{code}]: {message}")


class BinanceFuturesClient:
    """
    REST client for the Binance Futures USDT-M Testnet.

    Handles HMAC-SHA256 signing, injects the API key header into every
    request, logs requests/responses, and raises BinanceClientError when
    the exchange returns an error in the JSON body.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._session = requests.Session()
        self._session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        logger.debug("BinanceFuturesClient initialised | base_url=%s", self.base_url)

    # ---- signing helpers ----

    def _timestamp_ms(self) -> int:
        return int(time.time() * 1000)

    def _sign(self, params: Dict[str, Any]) -> str:
        """Sign the param dict with HMAC-SHA256 and return hex digest."""
        query = urllib.parse.urlencode(params)
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    # ---- core request method ----

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = True,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request and return the parsed JSON body.

        Adds timestamp + signature for signed endpoints.
        Raises BinanceClientError on API-level errors, or
        requests.RequestException on network failures.
        """
        params = params or {}

        if signed:
            params["timestamp"] = self._timestamp_ms()
            params["signature"] = self._sign(params)

        url = f"{self.base_url}{endpoint}"

        # log everything except the signature itself
        logger.info(
            "→ %s %s | params=%s",
            method.upper(),
            endpoint,
            {k: v for k, v in params.items() if k != "signature"},
        )

        try:
            if method.upper() in ("GET", "DELETE"):
                resp = self._session.request(method, url, params=params, timeout=self.timeout)
            else:
                resp = self._session.request(method, url, data=params, timeout=self.timeout)
        except requests.exceptions.Timeout:
            logger.error("Request timed out | url=%s", url)
            raise
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network error | url=%s | %s", url, exc)
            raise

        logger.debug(
            "← HTTP %s | url=%s | body=%s",
            resp.status_code,
            url,
            resp.text[:500],
        )

        try:
            data: Dict[str, Any] = resp.json()
        except ValueError:
            logger.error(
                "Non-JSON response | status=%s | body=%s",
                resp.status_code,
                resp.text[:200],
            )
            resp.raise_for_status()
            return {}

        # Binance uses a negative 'code' field for errors
        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            raise BinanceClientError(
                code=data.get("code", -1),
                message=data.get("msg", "Unknown error"),
            )

        if not resp.ok:
            logger.error("HTTP error | status=%s | body=%s", resp.status_code, data)
            resp.raise_for_status()

        logger.info("← Response OK | status=%s", resp.status_code)
        return data

    # ---- public methods ----

    def get_exchange_info(self) -> Dict[str, Any]:
        """Fetch exchange info (symbols, filters, rate limits, etc.)."""
        return self._request("GET", "/fapi/v1/exchangeInfo", signed=False)

    def get_account(self) -> Dict[str, Any]:
        """Fetch futures account info and asset balances."""
        return self._request("GET", "/fapi/v2/account")

    def place_order(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Submit a new order to Binance Futures.

        Accepts any Binance API order params as keyword args:
        symbol, side, type, quantity, price, stopPrice, timeInForce, etc.
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        return self._request("POST", "/fapi/v1/order", params=params)

    def close(self):
        """Close the underlying requests session."""
        self._session.close()
        logger.debug("HTTP session closed.")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
