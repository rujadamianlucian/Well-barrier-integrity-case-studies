"""Digital-twin wrapper: time-stepping, history recording and status queries."""

from __future__ import annotations

from collections.abc import Callable

from .core import Component
from .well import Well, WellConditions

ConditionsLike = WellConditions | Callable[[float], WellConditions]


class DigitalTwin:
    def __init__(self, well: Well):
        self.well = well
        self.time = 0.0  # s
        self.history: list[dict[str, float | bool]] = []
        self.record()

    def step(self, conditions: WellConditions, dt: float) -> None:
        self.well.step(conditions, dt)
        self.time += dt

    def run(
        self,
        conditions: ConditionsLike,
        *,
        duration: float,
        dt: float,
        record_every: int = 1,
    ) -> None:
        """Step for ``duration`` seconds in increments of ``dt``.

        ``conditions`` is either fixed or a function of time (s) returning
        ``WellConditions``. State is recorded after every ``record_every`` steps.
        """
        n_steps = int(round(duration / dt))
        for i in range(n_steps):
            current = conditions(self.time) if callable(conditions) else conditions
            self.step(current, dt)
            if (i + 1) % record_every == 0:
                self.record()

    def record(self) -> None:
        """Append the current state of every component to ``history``."""
        row: dict[str, float | bool] = {"time": self.time}
        for component in self.well.components:
            row[f"{component.name}.health"] = component.state.health
            row[f"{component.name}.failed"] = component.state.failed
            for key, value in component.state.variables.items():
                row[f"{component.name}.{key}"] = value
        for name, failed in self.barrier_status().items():
            row[f"barrier:{name}"] = failed
        self.history.append(row)

    def history_table(self) -> dict[str, list[float | bool]]:
        """History as ``{column: [values over time]}``, ready for numpy or pandas."""
        if not self.history:
            return {}
        return {key: [row[key] for row in self.history] for key in self.history[0]}

    def failed_components(self) -> list[Component]:
        return [
            component
            for component in self.well.components
            if component.state.failed
        ]

    def barrier_status(self) -> dict[str, bool]:
        return {
            barrier.name: barrier.failed
            for barrier in self.well.barriers
        }
