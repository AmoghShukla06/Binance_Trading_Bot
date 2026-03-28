#!/usr/bin/env python3
"""
Binance Futures Testnet – Enhanced Trading Bot CLI

Supports both flag-based and interactive (menu-driven) modes.

Examples:
  python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 1
  python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --quantity 1 --price 80000
  python cli.py account
  python cli.py  # launches interactive menu
"""
import os
import sys

import click
import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich import box
from rich.text import Text

from bot.client import BinanceClientError, BinanceFuturesClient
from bot.logging_config import setup_logging
from bot.orders import format_order_response, format_request_summary, place_order
from bot.validators import validate_all

console = Console()


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_client(api_key, api_secret):
    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


def _resolve_credentials(api_key, api_secret):
    """Pull credentials from CLI args or env vars, exit with a clear error if missing."""
    api_key = api_key or os.environ.get("BINANCE_API_KEY")
    api_secret = api_secret or os.environ.get("BINANCE_API_SECRET")

    if not api_key:
        console.print(Panel(
            "[bold red]✗ API key not found.[/]\n"
            "Set it via [yellow]--api-key[/] or [yellow]BINANCE_API_KEY[/] env var.",
            title="[red]Missing Credential[/]", border_style="red"
        ))
        sys.exit(1)
    if not api_secret:
        console.print(Panel(
            "[bold red]✗ API secret not found.[/]\n"
            "Set it via [yellow]--api-secret[/] or [yellow]BINANCE_API_SECRET[/] env var.",
            title="[red]Missing Credential[/]", border_style="red"
        ))
        sys.exit(1)

    return api_key, api_secret


def _print_banner():
    console.print(Panel(
        "[bold cyan]Binance Futures Testnet[/]  [dim]USDT-M Perpetuals[/]\n"
        "[dim]Type [/][yellow]help[/][dim] at any prompt to see available values[/]",
        title="[bold green]⚡ Trading Bot[/]",
        border_style="cyan",
        padding=(0, 2),
    ))


def _prompt_order_params():
    """Interactively prompt the user for all order parameters."""
    console.print("\n[bold cyan]── Order Setup ──[/]")

    symbol = Prompt.ask(
        "[yellow]Symbol[/]",
        default="BTCUSDT",
        console=console,
    ).strip().upper()

    side = Prompt.ask(
        "[yellow]Side[/]",
        choices=["BUY", "SELL"],
        console=console,
    ).upper()

    order_type = Prompt.ask(
        "[yellow]Order type[/]",
        choices=["MARKET", "LIMIT", "STOP_MARKET"],
        console=console,
    ).upper()

    quantity = Prompt.ask("[yellow]Quantity[/]", console=console)

    price = None
    stop_price = None

    if order_type == "LIMIT":
        price = Prompt.ask("[yellow]Limit price[/]", console=console)
    elif order_type == "STOP_MARKET":
        stop_price = Prompt.ask("[yellow]Stop trigger price[/]", console=console)

    return symbol, side, order_type, quantity, price, stop_price


def _show_validation_error(msg: str):
    console.print(Panel(
        f"[bold red]{msg}[/]",
        title="[red]Validation Error[/]",
        border_style="red",
    ))


def _show_api_error(code: int, message: str):
    console.print(Panel(
        f"[bold red]Code:[/] {code}\n[bold red]Message:[/] {message}",
        title="[red]Binance API Error[/]",
        border_style="red",
    ))


def _print_order_summary_rich(symbol, side, order_type, quantity, price, stop_price):
    table = Table(box=box.ROUNDED, border_style="cyan", show_header=False, padding=(0, 2))
    table.add_column("Field", style="bold white")
    table.add_column("Value", style="cyan")
    table.add_row("Symbol",     symbol)
    table.add_row("Side",       f"[green]{side}[/]" if side == "BUY" else f"[red]{side}[/]")
    table.add_row("Type",       order_type)
    table.add_row("Quantity",   quantity)
    table.add_row("Price",      price or "[dim]N/A (Market)[/]")
    table.add_row("Stop Price", stop_price or "[dim]N/A[/]")
    console.print(Panel(table, title="[bold]Order Preview[/]", border_style="cyan"))


def _print_order_response_rich(response: dict):
    table = Table(box=box.ROUNDED, border_style="green", show_header=False, padding=(0, 2))
    table.add_column("Field", style="bold white")
    table.add_column("Value", style="bright_green")

    side = response.get("side", "N/A")
    side_styled = f"[green]{side}[/]" if side == "BUY" else f"[red]{side}[/]"

    table.add_row("Order ID",      str(response.get("orderId", "N/A")))
    table.add_row("Client Ord ID", response.get("clientOrderId", "N/A"))
    table.add_row("Symbol",        response.get("symbol", "N/A"))
    table.add_row("Side",          side_styled)
    table.add_row("Type",          response.get("type", "N/A"))
    table.add_row("Status",        f"[bold yellow]{response.get('status', 'N/A')}[/]")
    table.add_row("Orig Qty",      str(response.get("origQty", "N/A")))
    table.add_row("Executed Qty",  str(response.get("executedQty", "N/A")))
    table.add_row("Avg Price",     str(response.get("avgPrice", "N/A")))
    table.add_row("Price",         str(response.get("price", "N/A")))
    table.add_row("Stop Price",    str(response.get("stopPrice", "N/A")))
    table.add_row("Time in Force", response.get("timeInForce", "N/A"))
    table.add_row("Reduce Only",   str(response.get("reduceOnly", "N/A")))

    console.print(Panel(table, title="[bold green]✓ Order Confirmed[/]", border_style="green"))


# ── root group ────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--api-key",    envvar="BINANCE_API_KEY",    default=None,
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
    ctx.obj["api_key"]  = api_key
    ctx.obj["api_secret"] = api_secret
    ctx.obj["logger"]   = setup_logging(log_level)

    # If no subcommand given, launch interactive menu
    if ctx.invoked_subcommand is None:
        _run_interactive_menu(ctx)


# ── interactive menu ──────────────────────────────────────────────────────────

def _run_interactive_menu(ctx):
    """Full interactive menu mode – prompts for everything."""
    _print_banner()

    api_key, api_secret = _resolve_credentials(ctx.obj["api_key"], ctx.obj["api_secret"])
    log = ctx.obj["logger"]

    while True:
        console.print("\n[bold cyan]What would you like to do?[/]")
        action = Prompt.ask(
            "[yellow]Action[/]",
            choices=["place", "account", "quit"],
            console=console,
        )

        if action == "quit":
            console.print("[dim]Bye![/]")
            break

        elif action == "account":
            ctx.invoke(account)

        elif action == "place":
            try:
                symbol, side, order_type, quantity, price, stop_price = _prompt_order_params()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Cancelled.[/]")
                continue

            try:
                validated = validate_all(
                    symbol=symbol, side=side, order_type=order_type,
                    quantity=quantity, price=price, stop_price=stop_price,
                )
            except ValueError as exc:
                _show_validation_error(str(exc))
                log.error("Validation error: %s", exc)
                continue

            _print_order_summary_rich(
                symbol=validated["symbol"],
                side=validated["side"],
                order_type=validated["type"],
                quantity=validated["quantity"],
                price=validated["price"],
                stop_price=validated["stopPrice"],
            )

            if not Confirm.ask("[yellow]Send this order?[/]", default=True, console=console):
                console.print("[yellow]Order cancelled.[/]")
                log.info("Order cancelled by user.")
                continue

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
                        time_in_force="GTC",
                    )
                _print_order_response_rich(response)

            except BinanceClientError as exc:
                log.error("Binance API error: [%s] %s", exc.code, exc.message)
                _show_api_error(exc.code, exc.message)
            except requests.exceptions.Timeout:
                log.error("Request timed out.")
                console.print("[red]✗ Request timed out. Please retry.[/]")
            except requests.exceptions.ConnectionError as exc:
                log.error("Network error: %s", exc)
                console.print("[red]✗ Network error. Check your connection.[/]")
            except Exception as exc:
                log.exception("Unexpected error.")
                console.print(f"[red]✗ Unexpected error: {exc}[/]")


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

    # validate
    try:
        validated = validate_all(
            symbol=symbol, side=side, order_type=order_type,
            quantity=quantity, price=price, stop_price=stop_price,
        )
    except ValueError as exc:
        log.error("Validation error: %s", exc)
        _show_validation_error(str(exc))
        sys.exit(1)

    # preview
    _print_order_summary_rich(
        symbol=validated["symbol"],
        side=validated["side"],
        order_type=validated["type"],
        quantity=validated["quantity"],
        price=validated["price"],
        stop_price=validated["stopPrice"],
    )

    if not Confirm.ask("[yellow]Send this order?[/]", default=True, console=console):
        console.print("[yellow]\nOrder cancelled by user.[/]")
        log.info("Order cancelled by user before submission.")
        sys.exit(0)

    # send
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

        _print_order_response_rich(response)

    except BinanceClientError as exc:
        log.error("Binance API error: [%s] %s", exc.code, exc.message)
        _show_api_error(exc.code, exc.message)
        sys.exit(1)
    except requests.exceptions.Timeout:
        log.error("Request timed out while placing order.")
        console.print("[red]✗ Request timed out. Please retry.[/]")
        sys.exit(1)
    except requests.exceptions.ConnectionError as exc:
        log.error("Network error: %s", exc)
        console.print("[red]✗ Network error. Check your connection and try again.[/]")
        sys.exit(1)
    except Exception as exc:
        log.exception("Unexpected error while placing order.")
        console.print(f"[red]✗ Unexpected error: {exc}[/]")
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

        table = Table(
            title="Account Balances (non-zero)",
            box=box.ROUNDED,
            border_style="cyan",
            header_style="bold cyan",
        )
        table.add_column("Asset",          style="bold white")
        table.add_column("Wallet Balance", style="green")
        table.add_column("Available",      style="bright_green")
        table.add_column("Unrealized PnL", style="yellow")

        if not non_zero:
            console.print("[dim]No assets with a non-zero balance.[/]")
        else:
            for a in non_zero:
                table.add_row(
                    a["asset"],
                    a.get("walletBalance", "N/A"),
                    a.get("availableBalance", "N/A"),
                    a.get("unrealizedProfit", "N/A"),
                )
            console.print(table)

    except BinanceClientError as exc:
        log.error("Binance API error: [%s] %s", exc.code, exc.message)
        _show_api_error(exc.code, exc.message)
        sys.exit(1)
    except requests.exceptions.RequestException as exc:
        log.error("Network error: %s", exc)
        console.print(f"[red]✗ Network error: {exc}[/]")
        sys.exit(1)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli(obj={})
