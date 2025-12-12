"""Command-line interface for the calculator."""

import click
from calculator import operations
from calculator.history import CalculationHistory

# Global history instance
_history = CalculationHistory()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """A simple CLI calculator with history support."""
    pass


@cli.command()
@click.argument("a", type=float)
@click.argument("b", type=float)
def add(a: float, b: float):
    """Add two numbers."""
    result = operations.add(a, b)
    expr = f"{a} + {b}"
    _history.add(expr, result)
    click.echo(f"{expr} = {result}")


@cli.command()
@click.argument("a", type=float)
@click.argument("b", type=float)
def subtract(a: float, b: float):
    """Subtract second number from first."""
    result = operations.subtract(a, b)
    expr = f"{a} - {b}"
    _history.add(expr, result)
    click.echo(f"{expr} = {result}")


@cli.command()
@click.argument("a", type=float)
@click.argument("b", type=float)
def multiply(a: float, b: float):
    """Multiply two numbers."""
    result = operations.multiply(a, b)
    expr = f"{a} * {b}"
    _history.add(expr, result)
    click.echo(f"{expr} = {result}")


@cli.command()
@click.argument("a", type=float)
@click.argument("b", type=float)
def divide(a: float, b: float):
    """Divide first number by second."""
    try:
        result = operations.divide(a, b)
        expr = f"{a} / {b}"
        _history.add(expr, result)
        click.echo(f"{expr} = {result}")
    except ZeroDivisionError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.option("--count", "-n", default=10, help="Number of entries to show")
def history(count: int):
    """Show calculation history."""
    entries = _history.get_last(count)
    if not entries:
        click.echo("No calculations in history.")
        return

    click.echo(f"Last {len(entries)} calculations:")
    for i, entry in enumerate(entries, 1):
        click.echo(f"  {i}. {entry}")


@cli.command()
def clear_history():
    """Clear calculation history."""
    _history.clear()
    click.echo("History cleared.")


if __name__ == "__main__":
    cli()
