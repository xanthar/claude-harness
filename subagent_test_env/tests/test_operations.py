"""Tests for calculator operations."""

import pytest
from calculator.operations import add, subtract, multiply, divide, power, modulo


class TestAddition:
    def test_add_positive_numbers(self):
        assert add(2, 3) == 5

    def test_add_negative_numbers(self):
        assert add(-2, -3) == -5

    def test_add_floats(self):
        assert add(1.5, 2.5) == 4.0


class TestSubtraction:
    def test_subtract_positive_numbers(self):
        assert subtract(5, 3) == 2

    def test_subtract_negative_result(self):
        assert subtract(3, 5) == -2


class TestMultiplication:
    def test_multiply_positive_numbers(self):
        assert multiply(3, 4) == 12

    def test_multiply_by_zero(self):
        assert multiply(5, 0) == 0


class TestDivision:
    def test_divide_evenly(self):
        assert divide(10, 2) == 5

    def test_divide_with_remainder(self):
        assert divide(7, 2) == 3.5

    def test_divide_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            divide(5, 0)


class TestPower:
    def test_power_positive(self):
        assert power(2, 3) == 8

    def test_power_zero_exponent(self):
        assert power(5, 0) == 1


class TestModulo:
    def test_modulo_positive(self):
        assert modulo(7, 3) == 1

    def test_modulo_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            modulo(5, 0)
