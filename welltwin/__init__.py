"""welltwin: modular well-integrity modelling.

Physical components, axial well segments, barrier envelopes, degradation models
and a digital-twin wrapper, kept separate from one another.
"""

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
    Tubular,
    Valve,
)
from .core import BarrierRole, Component, ComponentState, DegradationModel, Environment
from .degradation import ConstantRateLoss, StressEnhancedWallLoss
from .twin import DigitalTwin
from .well import (
    BarrierEnvelope,
    CasingSegment,
    ProductionTree,
    ReservoirSegment,
    Segment,
    SurfaceSegment,
    Well,
    WellConditions,
    Wellhead,
)

__all__ = [
    "Annulus",
    "AnnulusValve",
    "BarrierEnvelope",
    "BarrierRole",
    "Casing",
    "CasingSegment",
    "Cement",
    "Component",
    "ComponentState",
    "ConstantRateLoss",
    "DegradationModel",
    "DHSV",
    "DigitalTwin",
    "Environment",
    "Formation",
    "Packer",
    "ProductionTree",
    "ReservoirSegment",
    "SealAssembly",
    "Segment",
    "StressEnhancedWallLoss",
    "SurfaceSegment",
    "TreeValve",
    "Tubing",
    "Tubular",
    "Valve",
    "Well",
    "WellConditions",
    "Wellhead",
]
