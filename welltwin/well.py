"""Assemblies, axial segments, barrier envelopes and the whole-well container."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .components import (
    DHSV,
    Annulus,
    AnnulusValve,
    Casing,
    Cement,
    Formation,
    Packer,
    SealAssembly,
    TreeValve,
    Tubing,
)
from .core import BarrierRole, Component, Environment


# ---------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class WellConditions:
    """What the outside world imposes on the well at one moment (gauge, SI).

    ``tubing_pressure`` is the pressure in the tubing *at packer depth*.
    ``casing_external_pressure`` is the pressure outside the production casing at
    the top of the annulus; 0 means "ignore back-up load", which is conservative
    for burst.
    """

    tubing_pressure: float
    casing_external_pressure: float = 0.0
    temperature: float = 293.15

    def neutral_environment(self) -> Environment:
        """Zero net load. Placeholder for segments without their own physics."""
        return Environment(
            internal_pressure=self.tubing_pressure,
            external_pressure=self.tubing_pressure,
            temperature=self.temperature,
        )


# ---------------------------------------------------------------------
# Assemblies
# ---------------------------------------------------------------------

@dataclass
class Wellhead:
    casing_hanger_seal: SealAssembly
    tubing_hanger_seal: SealAssembly
    annulus_valve: AnnulusValve

    @property
    def components(self) -> list[Component]:
        return [
            self.casing_hanger_seal,
            self.tubing_hanger_seal,
            self.annulus_valve,
        ]


@dataclass
class ProductionTree:
    master_valve: TreeValve
    wing_valve: TreeValve
    connector_seal: SealAssembly

    @property
    def components(self) -> list[Component]:
        return [
            self.master_valve,
            self.wing_valve,
            self.connector_seal,
        ]


# ---------------------------------------------------------------------
# Axial well segments
# ---------------------------------------------------------------------

class Segment(ABC):
    """A stretch of the well. A segment decides which environment each of its
    components sees; the default gives them all a neutral (zero net load) one."""

    @property
    @abstractmethod
    def components(self) -> list[Component]:
        ...

    def step(self, conditions: WellConditions, dt: float) -> None:
        environment = conditions.neutral_environment()
        for component in self.components:
            component.step(environment, dt)


@dataclass
class SurfaceSegment(Segment):
    wellhead: Wellhead
    production_tree: ProductionTree

    @property
    def components(self) -> list[Component]:
        return self.wellhead.components + self.production_tree.components


@dataclass
class CasingSegment(Segment):
    """Tubing, packer, A-annulus and production casing.

    This is where components are coupled. In one step:

    1. the packer degrades and sees tubing pressure inside, annulus pressure outside;
    2. the annulus pressure relaxes towards tubing pressure through the packer's leak path;
    3. the tubing sees tubing pressure inside and the new annulus pressure outside;
    4. the production casing, cement and formation see the annulus pressure at the
       *top* of the annulus inside and ``casing_external_pressure`` outside.

    Steps 1-2 are operator-split (first order in dt).
    """

    tubing: Tubing
    production_casing: Casing
    casing_cement: Cement
    formation: Formation
    packer: Packer
    annulus: Annulus

    @property
    def components(self) -> list[Component]:
        return [
            self.tubing,
            self.production_casing,
            self.casing_cement,
            self.formation,
            self.packer,
            self.annulus,
        ]

    def step(self, conditions: WellConditions, dt: float) -> None:
        p_tubing = conditions.tubing_pressure
        p_outside = conditions.casing_external_pressure
        temperature = conditions.temperature

        self.packer.step(
            Environment(
                internal_pressure=p_tubing,
                external_pressure=self.annulus.pressure,
                temperature=temperature,
            ),
            dt,
        )

        self.annulus.relax_towards(p_tubing, self.packer.leak_conductance, dt)
        self.annulus.step(
            Environment(
                internal_pressure=self.annulus.pressure,
                external_pressure=p_outside,
                temperature=temperature,
            ),
            dt,
        )

        self.tubing.step(
            Environment(
                internal_pressure=p_tubing,
                external_pressure=self.annulus.pressure,
                temperature=temperature,
            ),
            dt,
        )

        casing_environment = Environment(
            internal_pressure=self.annulus.top_pressure,
            external_pressure=p_outside,
            temperature=temperature,
        )
        for component in (self.production_casing, self.casing_cement, self.formation):
            component.step(casing_environment, dt)


@dataclass
class ReservoirSegment(Segment):
    completion_string: Tubing
    dhsv: DHSV
    caprock: Formation

    @property
    def components(self) -> list[Component]:
        return [
            self.completion_string,
            self.dhsv,
            self.caprock,
        ]


# ---------------------------------------------------------------------
# Barrier envelopes
# ---------------------------------------------------------------------

@dataclass
class BarrierEnvelope:
    name: str
    components: list[Component]

    @property
    def failed_components(self) -> list[Component]:
        return [c for c in self.components if c.state.failed]

    @property
    def failed(self) -> bool:
        """Very simple starting rule: the envelope is failed if any member has
        failed (a series system). Replace with graph/path logic later."""
        return bool(self.failed_components)


# ---------------------------------------------------------------------
# Whole well
# ---------------------------------------------------------------------

@dataclass
class Well:
    surface: SurfaceSegment
    casing: CasingSegment
    reservoir: ReservoirSegment
    barriers: list[BarrierEnvelope] = field(default_factory=list)

    def __post_init__(self) -> None:
        names = [component.name for component in self.components]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"component names must be unique, duplicated: {duplicates}")

    @property
    def segments(self) -> list[Segment]:
        return [self.surface, self.casing, self.reservoir]

    @property
    def components(self) -> list[Component]:
        items: list[Component] = []
        for segment in self.segments:
            items.extend(segment.components)
        return items

    def get(self, name: str) -> Component:
        """Look a component up by name."""
        for component in self.components:
            if component.name == name:
                return component
        raise KeyError(name)

    def barriers_from_roles(self) -> list[BarrierEnvelope]:
        """Build one envelope per ``BarrierRole`` from the components' roles."""
        envelopes = []
        for role in (BarrierRole.PRIMARY, BarrierRole.SECONDARY):
            members = [c for c in self.components if role in c.barrier_roles]
            if members:
                envelopes.append(BarrierEnvelope(f"{role.name.title()} envelope", members))
        return envelopes

    def step(self, conditions: WellConditions, dt: float) -> None:
        """Advance every segment by ``dt`` seconds under the given conditions."""
        for segment in self.segments:
            segment.step(conditions, dt)
