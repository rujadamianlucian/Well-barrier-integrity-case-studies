"""Degradation models. Each one maps (state, environment, dt) -> new state."""

from __future__ import annotations

from dataclasses import dataclass

from .core import ComponentState, Environment


@dataclass(frozen=True)
class ConstantRateLoss:
    """Reduce one state variable at a constant rate, floored at zero.

    ``rate`` is in variable-units per second. Example: a packer seal that goes
    from 1 to 0 over ten years is ``ConstantRateLoss("seal_integrity", 1 / (10 * YEAR))``.
    """

    variable: str
    rate: float

    def step(
        self,
        state: ComponentState,
        environment: Environment,
        dt: float,
    ) -> ComponentState:
        value = max(state.variables[self.variable] - self.rate * dt, 0.0)
        return state.with_variables(**{self.variable: value})


@dataclass(frozen=True)
class StressEnhancedWallLoss:
    """Wall loss whose rate increases with how heavily the wall is loaded.

        rate = base_rate * (1 + stress_factor * u ** stress_exponent)

    where ``u`` is the component's ``burst_utilisation`` clipped to [0, 1].

    This is a *phenomenological placeholder*. It says "more loaded wall corrodes
    faster" and nothing more. ``stress_factor`` is an assumption and the whole
    stress-driven acceleration in a result is proportional to it. Set it to 0
    for plain constant-rate corrosion. Requires the component to publish
    ``burst_utilisation`` (``Tubular`` does).
    """

    base_rate: float              # m/s at zero load
    stress_factor: float = 0.0
    stress_exponent: float = 1.0

    def step(
        self,
        state: ComponentState,
        environment: Environment,
        dt: float,
    ) -> ComponentState:
        u = min(max(state.variables["burst_utilisation"], 0.0), 1.0)
        rate = self.base_rate * (1.0 + self.stress_factor * u**self.stress_exponent)
        wall = max(state.variables["wall_thickness"] - rate * dt, 0.0)
        return state.with_variables(wall_thickness=wall)
