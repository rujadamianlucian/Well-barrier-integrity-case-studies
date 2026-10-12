"""Physical well components.

Every component carries its own ``ComponentState`` and decides for itself what
"failed" means. Loads come in through an ``Environment``.
"""

from __future__ import annotations

import math

from .core import BarrierRole, Component, ComponentState, Environment
from .units import G


# ---------------------------------------------------------------------
# Tubulars
# ---------------------------------------------------------------------

class Tubular(Component):
    """Base class for casing and tubing.

    Failure criterion: burst utilisation >= 1, i.e. the net internal pressure
    reaches the Barlow internal-yield pressure of the *current* (corroded)
    wall. Collapse and axial loads are not modelled yet.
    """

    def __init__(
        self,
        name: str,
        *,
        outer_diameter: float,
        wall_thickness: float,
        yield_strength: float,
        barrier_roles: set[BarrierRole] | None = None,
    ):
        if outer_diameter <= 0 or yield_strength <= 0:
            raise ValueError("outer_diameter and yield_strength must be positive")
        if not 0 < wall_thickness < outer_diameter / 2:
            raise ValueError("wall_thickness must be positive and less than the outer radius")

        self.outer_diameter = outer_diameter
        self.initial_wall_thickness = wall_thickness
        self.yield_strength = yield_strength

        super().__init__(name, barrier_roles=barrier_roles)

    def initial_state(self) -> ComponentState:
        return ComponentState(
            variables={
                "wall_thickness": self.initial_wall_thickness,
                "burst_utilisation": 0.0,
            }
        )

    @property
    def wall_thickness(self) -> float:
        return self.state.variables["wall_thickness"]

    @property
    def initial_inner_diameter(self) -> float:
        return self.outer_diameter - 2.0 * self.initial_wall_thickness

    @property
    def burst_rating(self) -> float:
        """Internal-yield pressure at the current wall thickness (Pa).

        Barlow with the 0.875 wall-tolerance factor, as in API 5C3:
        ``P = 0.875 * 2 * Yp * t / D``.
        """
        return 0.875 * 2.0 * self.yield_strength * self.wall_thickness / self.outer_diameter

    def observe(self, environment: Environment) -> None:
        load = max(environment.net_internal_pressure, 0.0)
        rating = self.burst_rating
        if rating > 0.0:
            utilisation = load / rating
        else:
            utilisation = math.inf if load > 0.0 else 0.0
        self.state.variables["burst_utilisation"] = utilisation
        self.state.health = max(self.wall_thickness / self.initial_wall_thickness, 0.0)

    def failure_condition(self, environment: Environment) -> bool:
        return (
            self.wall_thickness <= 0.0
            or self.state.variables["burst_utilisation"] >= 1.0
        )


class Casing(Tubular):
    """Casing string."""


class Tubing(Tubular):
    """Production tubing or completion string."""


# ---------------------------------------------------------------------
# Cement and formation
# ---------------------------------------------------------------------

class Cement(Component):
    def __init__(
        self,
        name: str,
        *,
        bond_quality: float = 1.0,
        permeability: float = 1e-18,
        barrier_roles: set[BarrierRole] | None = None,
    ):
        self.initial_bond_quality = bond_quality
        self.initial_permeability = permeability
        super().__init__(name, barrier_roles=barrier_roles)

    def initial_state(self) -> ComponentState:
        return ComponentState(
            variables={
                "bond_quality": self.initial_bond_quality,
                "permeability": self.initial_permeability,
            }
        )

    def observe(self, environment: Environment) -> None:
        self.state.health = self.state.variables["bond_quality"]

    def failure_condition(self, environment: Environment) -> bool:
        return self.state.variables["bond_quality"] <= 0.0


class Formation(Component):
    def __init__(
        self,
        name: str,
        *,
        fracture_pressure: float,
        permeability: float,
        barrier_roles: set[BarrierRole] | None = None,
    ):
        self.fracture_pressure = fracture_pressure
        self.permeability = permeability
        super().__init__(name, barrier_roles=barrier_roles)

    def initial_state(self) -> ComponentState:
        return ComponentState(variables={"permeability": self.permeability})

    def failure_condition(self, environment: Environment) -> bool:
        # Leave detailed geomechanics for later.
        return False


# ---------------------------------------------------------------------
# Packer, valves, seals
# ---------------------------------------------------------------------

class Packer(Component):
    """Production packer separating the tubing from the A-annulus.

    ``seal_integrity`` runs from 1 (new) to 0 (no sealing left). A degraded seal
    leaks according to a laminar-type law ``q = C * dp`` with a conductance that
    grows as the seal is lost:

        C = max_leak_conductance * (1 - seal_integrity) ** leak_exponent

    ``max_leak_conductance`` (m^3/s/Pa) and ``leak_exponent`` are shape
    parameters to be calibrated against leak-test data. They are assumptions,
    not measured properties.
    """

    def __init__(
        self,
        name: str,
        *,
        pressure_rating: float,
        max_leak_conductance: float = 1e-12,
        leak_exponent: float = 3.0,
        barrier_roles: set[BarrierRole] | None = None,
    ):
        if max_leak_conductance < 0 or leak_exponent <= 0:
            raise ValueError("max_leak_conductance must be >= 0 and leak_exponent > 0")
        self.pressure_rating = pressure_rating
        self.max_leak_conductance = max_leak_conductance
        self.leak_exponent = leak_exponent
        super().__init__(name, barrier_roles=barrier_roles)

    def initial_state(self) -> ComponentState:
        return ComponentState(
            variables={
                "seal_integrity": 1.0,
                "pressure_differential": 0.0,  # tubing side minus annulus side, Pa
                "leak_rate": 0.0,              # m^3/s, positive = tubing -> annulus
            }
        )

    @property
    def leak_conductance(self) -> float:
        """Current leak conductance (m^3/s/Pa)."""
        lost = 1.0 - self.state.variables["seal_integrity"]
        lost = min(max(lost, 0.0), 1.0)
        return self.max_leak_conductance * lost**self.leak_exponent

    def observe(self, environment: Environment) -> None:
        differential = environment.net_internal_pressure
        self.state.variables["pressure_differential"] = differential
        self.state.variables["leak_rate"] = self.leak_conductance * differential
        self.state.health = self.state.variables["seal_integrity"]

    def failure_condition(self, environment: Environment) -> bool:
        x = self.state.variables
        return (
            x["seal_integrity"] <= 0.0
            or abs(x["pressure_differential"]) > self.pressure_rating
        )


class Valve(Component):
    def __init__(
        self,
        name: str,
        *,
        pressure_rating: float,
        barrier_roles: set[BarrierRole] | None = None,
    ):
        self.pressure_rating = pressure_rating
        super().__init__(name, barrier_roles=barrier_roles)

    def initial_state(self) -> ComponentState:
        return ComponentState(
            variables={
                "seal_integrity": 1.0,
                "actuation_reliability": 1.0,
            }
        )

    def observe(self, environment: Environment) -> None:
        self.state.health = self.state.variables["seal_integrity"]

    def failure_condition(self, environment: Environment) -> bool:
        return self.state.variables["seal_integrity"] <= 0.0


class DHSV(Valve):
    """Downhole safety valve."""


class AnnulusValve(Valve):
    pass


class TreeValve(Valve):
    pass


class SealAssembly(Component):
    def __init__(
        self,
        name: str,
        *,
        pressure_rating: float,
        barrier_roles: set[BarrierRole] | None = None,
    ):
        self.pressure_rating = pressure_rating
        super().__init__(name, barrier_roles=barrier_roles)

    def initial_state(self) -> ComponentState:
        return ComponentState(
            variables={
                "seal_integrity": 1.0,
                "leak_rate": 0.0,
            }
        )

    def observe(self, environment: Environment) -> None:
        self.state.health = self.state.variables["seal_integrity"]

    def failure_condition(self, environment: Environment) -> bool:
        return self.state.variables["seal_integrity"] <= 0.0


# ---------------------------------------------------------------------
# Annulus
# ---------------------------------------------------------------------

class Annulus(Component):
    """Fluid-filled annulus, treated as one closed compressible volume.

    ``pressure`` is the pressure at the bottom of the annulus (packer depth).
    ``top_pressure`` is the pressure at the wellhead, i.e. what you would read on
    a gauge: ``pressure - fluid_density * g * height``. Sustained annulus
    pressure is a top-of-annulus quantity, and it is what loads the upper casing.

    With no leak path the volume is closed and the pressure stays put. Fluid
    entering through a leak raises the pressure by ``dp = (K / V) * dV``, where
    ``K`` is the effective bulk modulus (fluid plus the compliance of the
    surrounding steel, folded into one number).

    Not modelled yet: thermal expansion, bleed-down through the annulus valve,
    gas in the annulus, fluid losses to the formation.
    """

    def __init__(
        self,
        name: str,
        *,
        volume: float,
        height: float,
        fluid_density: float = 1030.0,
        bulk_modulus: float = 2.0e9,
        initial_top_pressure: float = 0.0,
        barrier_roles: set[BarrierRole] | None = None,
    ):
        if volume <= 0 or height <= 0 or fluid_density <= 0 or bulk_modulus <= 0:
            raise ValueError("volume, height, fluid_density and bulk_modulus must be positive")
        self.volume = volume
        self.height = height
        self.fluid_density = fluid_density
        self.bulk_modulus = bulk_modulus
        self.initial_top_pressure = initial_top_pressure
        super().__init__(name, barrier_roles=barrier_roles)

    @property
    def hydrostatic_pressure(self) -> float:
        """Pressure the fluid column adds between the top and bottom (Pa)."""
        return self.fluid_density * G * self.height

    def initial_state(self) -> ComponentState:
        return ComponentState(
            variables={
                "pressure": self.hydrostatic_pressure + self.initial_top_pressure,
                "top_pressure": self.initial_top_pressure,
                "leaked_volume": 0.0,  # net volume that has entered, m^3
            }
        )

    @property
    def pressure(self) -> float:
        return self.state.variables["pressure"]

    @property
    def top_pressure(self) -> float:
        return self.state.variables["top_pressure"]

    def relax_towards(self, source_pressure: float, conductance: float, dt: float) -> None:
        """Let the annulus exchange fluid with a source through a leak path.

        Solves ``dp/dt = (K / V) * C * (p_source - p)`` exactly over ``dt`` for a
        constant conductance ``C``. The exact exponential is used instead of an
        explicit step so that large timesteps cannot overshoot or oscillate.
        """
        if conductance < 0 or dt < 0:
            raise ValueError("conductance and dt must be non-negative")
        old = self.pressure
        rate = self.bulk_modulus * conductance / self.volume
        new = source_pressure + (old - source_pressure) * math.exp(-rate * dt)
        self.state.variables["pressure"] = new
        self.state.variables["leaked_volume"] += self.volume / self.bulk_modulus * (new - old)

    def observe(self, environment: Environment) -> None:
        self.state.variables["top_pressure"] = self.pressure - self.hydrostatic_pressure

    def failure_condition(self, environment: Environment) -> bool:
        # The annulus is a fluid volume, not a barrier element. Its pressure
        # is judged through the components that carry the load.
        return False
