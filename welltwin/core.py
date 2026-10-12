"""Core abstractions: environment, state, the component base class and the
degradation-model interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from typing import Protocol


class BarrierRole(Enum):
    """Which barrier envelope a component belongs to."""

    PRIMARY = auto()
    SECONDARY = auto()


@dataclass(frozen=True)
class Environment:
    """Conditions acting on one component during one step (SI, gauge pressure).

    ``internal_pressure`` and ``external_pressure`` are the pressures on the two
    sides of the component. What "inside" means depends on the component: for a
    tubular it is the bore, for a packer it is the tubing side.
    """

    internal_pressure: float = 0.0
    external_pressure: float = 0.0
    temperature: float = 293.15  # K. Not yet used by any model.
    fluid: str | None = None

    @property
    def net_internal_pressure(self) -> float:
        """Pressure difference pushing outwards (positive = burst direction)."""
        return self.internal_pressure - self.external_pressure


@dataclass
class ComponentState:
    """Generic state container for a physical well component."""

    health: float = 1.0
    failed: bool = False
    variables: dict[str, float] = field(default_factory=dict)

    def with_variables(self, **updates: float) -> ComponentState:
        """Return a copy of this state with some variables replaced."""
        return replace(self, variables={**self.variables, **updates})


class DegradationModel(Protocol):
    """Anything that can advance a component's state by one timestep.

    A model must not mutate the state it is given; it returns a new one.
    """

    def step(
        self,
        state: ComponentState,
        environment: Environment,
        dt: float,
    ) -> ComponentState:
        ...


class Component(ABC):
    """Base class for anything with its own physical integrity state."""

    def __init__(
        self,
        name: str,
        *,
        barrier_roles: set[BarrierRole] | None = None,
    ):
        self.name = name
        self.barrier_roles: set[BarrierRole] = set(barrier_roles or ())
        self.state = self.initial_state()
        self.degradation_models: list[DegradationModel] = []

    @abstractmethod
    def initial_state(self) -> ComponentState:
        """State of the component when new."""

    @abstractmethod
    def failure_condition(self, environment: Environment) -> bool:
        """Whether the component has lost its function in this environment."""

    def observe(self, environment: Environment) -> None:
        """Refresh derived quantities (loads, utilisation, health) from the
        current state and environment. Default: nothing to derive."""

    def add_degradation_model(self, model: DegradationModel) -> Component:
        """Attach a degradation model. Returns ``self`` so calls can be chained."""
        self.degradation_models.append(model)
        return self

    def step(self, environment: Environment, dt: float) -> None:
        """Advance this component by one timestep of ``dt`` seconds."""
        self.observe(environment)
        for model in self.degradation_models:
            self.state = model.step(self.state, environment, dt)
        self.observe(environment)
        self.state.failed = self.failure_condition(environment)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r}, failed={self.state.failed})"
