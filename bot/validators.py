from decimal import Decimal, InvalidOperation
from typing import Optional

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}


def validate_symbol(symbol: str) -> str:
    """Strip whitespace, uppercase, and check that the symbol is alphanumeric."""
    symbol = symbol.strip().upper()
    if not symbol or not symbol.isalnum():
        raise ValueError(f"Invalid symbol '{symbol}'. Must be alphanumeric, e.g. BTCUSDT.")
    return symbol


def validate_side(side: str) -> str:
    """Check that side is BUY or SELL."""
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(f"Invalid side '{side}'. Choose BUY or SELL.")
    return side


def validate_order_type(order_type: str) -> str:
    """Check that the order type is one of the supported types."""
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. "
            f"Supported types: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return order_type


def validate_quantity(quantity) -> str:
    """Make sure quantity is a positive number."""
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValueError(f"Invalid quantity '{quantity}'. Must be a positive number.")
    if qty <= 0:
        raise ValueError(f"Quantity must be greater than zero, got {quantity}.")
    return str(qty)


def validate_price(price: Optional[str], order_type: str) -> Optional[str]:
    """
    Validate the price field based on order type.
    LIMIT orders require a positive price.
    MARKET orders don't use price at all (returns None).
    """
    if order_type in ("MARKET", "STOP_MARKET"):
        return None

    if price is None:
        raise ValueError(f"Price is required for {order_type} orders.")

    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValueError(f"Invalid price '{price}'. Must be a positive number.")
    if p <= 0:
        raise ValueError(f"Price must be greater than zero, got {price}.")
    return str(p)


def validate_stop_price(stop_price: Optional[str], order_type: str) -> Optional[str]:
    """Validate stopPrice for STOP_MARKET orders. Returns None for other types."""
    if order_type != "STOP_MARKET":
        return None
    if stop_price is None:
        raise ValueError("stopPrice is required for STOP_MARKET orders.")
    try:
        sp = Decimal(str(stop_price))
    except InvalidOperation:
        raise ValueError(f"Invalid stop price '{stop_price}'. Must be a positive number.")
    if sp <= 0:
        raise ValueError(f"Stop price must be greater than zero, got {stop_price}.")
    return str(sp)


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity,
    price=None,
    stop_price=None,
) -> dict:
    """
    Run all validators and return a clean dict ready for the order client.
    Raises ValueError with a descriptive message on any invalid input.
    """
    v_symbol = validate_symbol(symbol)
    v_side = validate_side(side)
    v_type = validate_order_type(order_type)
    v_qty = validate_quantity(quantity)
    v_price = validate_price(price, v_type)
    v_stop = validate_stop_price(stop_price, v_type)

    return {
        "symbol": v_symbol,
        "side": v_side,
        "type": v_type,
        "quantity": v_qty,
        "price": v_price,
        "stopPrice": v_stop,
    }
