"""Calculation history management."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class CalculationRecord:
    """A single calculation record."""
    expression: str
    result: float
    timestamp: datetime

    def __str__(self) -> str:
        return f"{self.expression} = {self.result}"


class CalculationHistory:
    """Manages calculation history."""

    def __init__(self, max_size: int = 100):
        self._history: List[CalculationRecord] = []
        self._max_size = max_size

    def add(self, expression: str, result: float) -> None:
        """Add a calculation to history."""
        record = CalculationRecord(
            expression=expression,
            result=result,
            timestamp=datetime.now()
        )
        self._history.append(record)

        # Trim if exceeds max size
        if len(self._history) > self._max_size:
            self._history = self._history[-self._max_size:]

    def get_last(self, count: int = 10) -> List[CalculationRecord]:
        """Get the last N calculations."""
        return self._history[-count:]

    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()

    def search(self, term: str) -> List[CalculationRecord]:
        """Search history for expressions containing term."""
        return [r for r in self._history if term in r.expression]

    @property
    def size(self) -> int:
        """Return current history size."""
        return len(self._history)

    def get_by_index(self, index: int) -> Optional[CalculationRecord]:
        """Get a specific calculation by index."""
        if 0 <= index < len(self._history):
            return self._history[index]
        return None
