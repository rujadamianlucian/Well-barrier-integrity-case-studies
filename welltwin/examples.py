"""A ready-made example well for the case studies.

Geometry and steel grades are typical textbook values (4.5 in 12.6 lb/ft L80
tubing inside 9 5/8 in 47 lb/ft L80 casing). Everything else (leak shape,
corrosion rate, stress coupling, ratings, depths) is an illustrative assumption,
not data from any real well. The barrier-role assignment is illustrative and is
not an envelope definition from NORSOK D-010 or any other standard.
"""

from __future__ import annotations

import math

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
from .core import BarrierRole
from .degradation import ConstantRateLoss, StressEnhancedWallLoss
from .units import INCH, MM, MPA, PSI, YEAR
from .well import (
    CasingSegment,
    ProductionTree,
    ReservoirSegment,
    SurfaceSegment,
    Well,
    Wellhead,
)


def build_example_well(
    *,
    packer_life_years: float | None = 10.0,
    corrosion_mm_per_year: float = 0.1,
    stress_factor: float = 5.0,
    stress_exponent: float = 1.0,
    max_leak_conductance: float = 1e-12,
    leak_exponent: float = 3.0,
    packer_depth: float = 3000.0,
) -> Well:
    """Build the example well.

    Parameters
    ----------
    packer_life_years
        Time over which the packer's ``seal_integrity`` falls linearly from 1 to 0.
        ``None`` gives a packer that does not degrade (the healthy reference case).
    corrosion_mm_per_year
        Baseline production-casing wall loss at zero load.
    stress_factor, stress_exponent
        Load dependence of wall loss, see ``StressEnhancedWallLoss``. Assumed.
    max_leak_conductance, leak_exponent
        Packer leak shape, see ``Packer``. Assumed.
    packer_depth
        Height of the A-annulus fluid column (m).
    """
    primary, secondary = BarrierRole.PRIMARY, BarrierRole.SECONDARY
    grade_l80 = 80_000 * PSI  # minimum yield strength

    tubing = Tubing(
        "Tubing",
        outer_diameter=4.5 * INCH,
        wall_thickness=0.271 * INCH,
        yield_strength=grade_l80,
        barrier_roles={primary},
    )
    casing = Casing(
        "Production casing",
        outer_diameter=9.625 * INCH,
        wall_thickness=0.472 * INCH,
        yield_strength=grade_l80,
        barrier_roles={secondary},
    )
    casing.add_degradation_model(
        StressEnhancedWallLoss(
            base_rate=corrosion_mm_per_year * MM / YEAR,
            stress_factor=stress_factor,
            stress_exponent=stress_exponent,
        )
    )

    packer = Packer(
        "Packer",
        pressure_rating=10_000 * PSI,
        max_leak_conductance=max_leak_conductance,
        leak_exponent=leak_exponent,
        barrier_roles={primary},
    )
    if packer_life_years is not None:
        packer.add_degradation_model(
            ConstantRateLoss("seal_integrity", 1.0 / (packer_life_years * YEAR))
        )

    annulus_area = math.pi / 4.0 * (casing.initial_inner_diameter**2 - tubing.outer_diameter**2)
    annulus = Annulus("A-annulus", volume=annulus_area * packer_depth, height=packer_depth)

    surface = SurfaceSegment(
        wellhead=Wellhead(
            casing_hanger_seal=SealAssembly(
                "Casing hanger seal", pressure_rating=10_000 * PSI, barrier_roles={secondary}
            ),
            tubing_hanger_seal=SealAssembly(
                "Tubing hanger seal", pressure_rating=10_000 * PSI, barrier_roles={primary}
            ),
            annulus_valve=AnnulusValve(
                "Annulus valve", pressure_rating=10_000 * PSI, barrier_roles={secondary}
            ),
        ),
        production_tree=ProductionTree(
            master_valve=TreeValve(
                "Master valve", pressure_rating=10_000 * PSI, barrier_roles={primary}
            ),
            wing_valve=TreeValve(
                "Wing valve", pressure_rating=10_000 * PSI, barrier_roles={primary}
            ),
            connector_seal=SealAssembly(
                "Connector seal", pressure_rating=10_000 * PSI, barrier_roles={primary}
            ),
        ),
    )
    casing_segment = CasingSegment(
        tubing=tubing,
        production_casing=casing,
        casing_cement=Cement("Casing cement", barrier_roles={secondary}),
        formation=Formation(
            "Formation", fracture_pressure=55 * MPA, permeability=1e-16, barrier_roles={secondary}
        ),
        packer=packer,
        annulus=annulus,
    )
    reservoir = ReservoirSegment(
        completion_string=Tubing(
            "Completion string",
            outer_diameter=4.5 * INCH,
            wall_thickness=0.271 * INCH,
            yield_strength=grade_l80,
            barrier_roles={primary},
        ),
        dhsv=DHSV("DHSV", pressure_rating=10_000 * PSI, barrier_roles={primary}),
        caprock=Formation(
            "Caprock", fracture_pressure=60 * MPA, permeability=1e-19, barrier_roles={primary}
        ),
    )

    well = Well(surface=surface, casing=casing_segment, reservoir=reservoir)
    well.barriers = well.barriers_from_roles()
    return well
