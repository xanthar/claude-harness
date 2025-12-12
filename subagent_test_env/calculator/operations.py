"""Basic mathematical operations for the calculator."""

from typing import Union

Number = Union[int, float]


def add(a: Number, b: Number) -> Number:
    """Add two numbers."""
    return a + b


def subtract(a: Number, b: Number) -> Number:
    """Subtract b from a."""
    return a - b


def multiply(a: Number, b: Number) -> Number:
    """Multiply two numbers."""
    return a * b


def divide(a: Number, b: Number) -> Number:
    """Divide a by b.

    Raises:
        ZeroDivisionError: If b is zero.
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


def power(base: Number, exponent: Number) -> Number:
    """Raise base to the power of exponent."""
    return base ** exponent


def modulo(a: Number, b: Number) -> Number:
    """Return the remainder of a divided by b.

    Raises:
        ZeroDivisionError: If b is zero.
    """
    if b == 0:
        raise ZeroDivisionError("Cannot modulo by zero")
    return a % b
