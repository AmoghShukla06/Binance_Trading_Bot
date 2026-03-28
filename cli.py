#!/usr/bin/env python3
"""
Binance Futures Testnet – Trading Bot CLI

Examples:
  python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 1
  python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --quantity 1 --price 80000
  python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 1 --stop-price 75000
  python cli.py account
"""
import os
import sys

import click
import requests

from bot.client import BinanceClientError, BinanceFuturesClient
from bot.logging_config import setup_logging
from bot.orders import format_order_response, format_request_summary, place_order
from bot.validators import validate_all


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_client(api_key, api_secret):
    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


def _resolve_credentials(api_key, api_secret):
    """Pull credentials from CLI args or env vars, exit if missing."""
    api_key = api_key or os.environ.get("BINANCE_API_KEY")
    api_secret = api_secret or os.environ.get("BINANCE_API_SECRET")

    if not api_key:
        click.echo(click.style("✗ API key missing. Use --api-key or set BINANCE_API_KEY.", fg="red"))
        sys.exit(1)
    if not api_secret:
        click.echo(click.style("✗ API secret missing. Use --api-secret or set BINANCE_API_SECRET.", fg="red"))
        sys.exit(1)

    return api_key, api_secret


# ── root group ───────────────────────────────────────────────────────────────

@click.group()
@click.option("--api-key", envvar="BINANCE_API_KEY", default=None,
              help="Binance API key (or set BINANCE_API_KEY env var).")
@click.option("--api-secret", envvar="BINANCE_API_SECRET", default=None,
              help="Binance API secret (or set BINANCE_API_SECRET env var).")
@click.option("--log-level", default="INFO", show_default=True,
              type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
              help="Logging verbosity.")
@click.pass_context
def cli(ctx, api_key, api_secret, log_level):
    """Binance Futures Testnet Trading Bot."""
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key
    ctx.obj["api_secret"] = api_secret
    ctx.obj["logger"] = setup_logging(log_level)


# ── place command ─────────────────────────────────────────────────────────────

@cli.command()
@click.option("--symbol",    required=True, help="Trading pair, e.g. BTCUSDT.")
@click.option("--side",      required=True,
              type=click.Choice(["BUY", "SELL"], case_sensitive=False),
              help="Order side.")
@click.option("--type", "order_type", required=True,
              type=click.Choice(["MARKET", "LIMIT", "STOP_MARKET"], case_sensitive=False),
              help="Order type.")
@click.option("--quantity",  required=True, help="Order quantity.")
@click.option("--price",     default=None,  help="Limit price (LIMIT orders only).")
@click.option("--stop-price", "stop_price", default=None,
              help="Stop trigger price (STOP_MARKET only).")
@click.option("--time-in-force", "time_in_force", default="GTC", show_default=True,
              type=click.Choice(["GTC", "IOC", "FOK"], case_sensitive=False),
              help="Time in force (LIMIT only).")
@click.option("--reduce-only", "reduce_only", is_flag=True, default=False,
              help="Mark as reduce-only.")
@click.pass_context
def place(ctx, symbol, side, order_type, quantity, price, stop_price, time_in_force, reduce_only):
    """Place a new order on Binance Futures Testnet."""
    log = ctx.obj["logger"]
    api_key, api_secret = _resolve_credentials(ctx.obj["api_key"], ctx.obj["api_secret"])

    # validate inputs
    try:
        validated = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
    except ValueError as exc:
        log.error("Validation error: %s", exc)
        click.echo(click.style(f"\n✗ Validation error: {exc}\n", fg="red"))
        sys.exit(1)

    # show summary and ask for confirmation
    click.echo(format_request_summary(
        symbol=validated["symbol"],
        side=validated["side"],
        order_type=validated["type"],
        quantity=validated["quantity"],
        price=validated["price"],
        stop_price=validated["stopPrice"],
    ))

    if not click.confirm(click.style("  Send this order?", fg="yellow"), default=True):
        click.echo(click.style("\n  Order cancelled by user.\n", fg="yellow"))
        log.info("Order cancelled by user before submission.")
        sys.exit(0)

    # send the order
    try:
        with _get_client(api_key, api_secret) as client:
            response = place_order(
                client=client,
                symbol=validated["symbol"],
                side=validated["side"],
                order_type=validated["type"],
                quantity=validated["quantity"],
                price=validated["price"],
                stop_price=validated["stopPrice"],
                time_in_force=time_in_force.upper(),
                reduce_only=reduce_only,
            )

        click.echo(format_order_response(response))
        click.echo(click.style("  ✓ Order placed successfully!\n", fg="green"))

    except BinanceClientError as exc:
        log.error("Binance API error: [%s] %s", exc.code, exc.message)
        click.echo(click.style(f"\n✗ Binance API Error [{exc.code}]: {exc.message}\n", fg="red"))
        sys.exit(1)

    except requests.exceptions.Timeout:
        log.error("Request timed out while placing order.")
        click.echo(click.style("\n✗ Request timed out. Please retry.\n", fg="red"))
        sys.exit(1)

    except requests.exceptions.ConnectionError as exc:
        log.error("Network error: %s", exc)
        click.echo(click.style("\n✗ Network error. Check your connection and try again.\n", fg="red"))
        sys.exit(1)

    except Exception as exc:
        log.exception("Unexpected error while placing order.")
        click.echo(click.style(f"\n✗ Unexpected error: {exc}\n", fg="red"))
        sys.exit(1)


# ── account command ───────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def account(ctx):
    """Display Binance Futures account balances."""
    log = ctx.obj["logger"]
    api_key, api_secret = _resolve_credentials(ctx.obj["api_key"], ctx.obj["api_secret"])

    try:
        with _get_client(api_key, api_secret) as client:
            data = client.get_account()

        assets = data.get("assets", [])
        non_zero = [a for a in assets if float(a.get("walletBalance", 0)) != 0]

        click.echo("\n" + "━" * 50)
        click.echo("  ACCOUNT BALANCES (non-zero assets)")
        click.echo("━" * 50)

        if not non_zero:
            click.echo("  No assets with a non-zero balance.")
        else:
            for asset in non_zero:
                click.echo(
                    f"  {asset['asset']:8s}  wallet={asset.get('walletBalance', 'N/A')}  "
                    f"available={asset.get('availableBalance', 'N/A')}  "
                    f"unrealizedPnL={asset.get('unrealizedProfit', 'N/A')}"
                )

        click.echo("━" * 50 + "\n")

    except BinanceClientError as exc:
        log.error("Binance API error: [%s] %s", exc.code, exc.message)
        click.echo(click.style(f"\n✗ Binance API Error [{exc.code}]: {exc.message}\n", fg="red"))
        sys.exit(1)

    except requests.exceptions.RequestException as exc:
        log.error("Network error: %s", exc)
        click.echo(click.style(f"\n✗ Network error: {exc}\n", fg="red"))
        sys.exit(1)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli(obj={})
