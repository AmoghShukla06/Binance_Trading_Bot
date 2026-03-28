import logging
from typing import Any, Dict, Optional

from .client import BinanceFuturesClient

logger = logging.getLogger("trading_bot.orders")


def _build_order_params(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
) -> Dict[str, Any]:
    """Build the params dict for a Binance Futures order request."""
    params: Dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": quantity,
    }

    if order_type == "LIMIT":
        params["price"] = price
        params["timeInForce"] = time_in_force
    elif order_type == "STOP_MARKET":
        params["stopPrice"] = stop_price

    if reduce_only:
        params["reduceOnly"] = "true"

    return params


def place_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str] = None,
    stop_price: Optional[str] = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
) -> Dict[str, Any]:
    """
    Place an order via the client and return the Binance response.

    Logs a summary before sending and after receiving the response.
    Raises BinanceClientError on API errors or requests.RequestException
    on network failures.
    """
    params = _build_order_params(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        time_in_force=time_in_force,
        reduce_only=reduce_only,
    )

    logger.info(
        "Placing %s %s order | symbol=%s | qty=%s | price=%s | stopPrice=%s",
        side,
        order_type,
        symbol,
        quantity,
        price or "N/A",
        stop_price or "N/A",
    )

    response = client.place_order(**params)

    logger.info(
        "Order placed successfully | orderId=%s | status=%s | executedQty=%s | avgPrice=%s",
        response.get("orderId", "N/A"),
        response.get("status", "N/A"),
        response.get("executedQty", "N/A"),
        response.get("avgPrice", "N/A"),
    )

    return response


def format_order_response(response: Dict[str, Any]) -> str:
    """Format a Binance order response dict into a readable string."""
    lines = [
        "",
        "━" * 50,
        "  ORDER RESPONSE",
        "━" * 50,
        f"  Order ID      : {response.get('orderId', 'N/A')}",
        f"  Client Ord ID : {response.get('clientOrderId', 'N/A')}",
        f"  Symbol        : {response.get('symbol', 'N/A')}",
        f"  Side          : {response.get('side', 'N/A')}",
        f"  Type          : {response.get('type', 'N/A')}",
        f"  Status        : {response.get('status', 'N/A')}",
        f"  Orig Qty      : {response.get('origQty', 'N/A')}",
        f"  Executed Qty  : {response.get('executedQty', 'N/A')}",
        f"  Avg Price     : {response.get('avgPrice', 'N/A')}",
        f"  Price         : {response.get('price', 'N/A')}",
        f"  Stop Price    : {response.get('stopPrice', 'N/A')}",
        f"  Time in Force : {response.get('timeInForce', 'N/A')}",
        f"  Reduce Only   : {response.get('reduceOnly', 'N/A')}",
        f"  Update Time   : {response.get('updateTime', 'N/A')}",
        "━" * 50,
        "",
    ]
    return "\n".join(lines)


def format_request_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str],
    stop_price: Optional[str],
) -> str:
    """Return a formatted pre-send summary of the order."""
    lines = [
        "",
        "━" * 50,
        "  ORDER REQUEST SUMMARY",
        "━" * 50,
        f"  Symbol     : {symbol}",
        f"  Side       : {side}",
        f"  Type       : {order_type}",
        f"  Quantity   : {quantity}",
        f"  Price      : {price or 'N/A (Market)'}",
        f"  Stop Price : {stop_price or 'N/A'}",
        "━" * 50,
        "",
    ]
    return "\n".join(lines)
