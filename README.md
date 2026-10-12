# WellTwin (`welltwin`)

A small Python library for modelling well integrity as a network: physical components, axial well segments, barrier envelopes, degradation models, and a digital-twin wrapper that steps them through time.

**Status: v0.1, a framework plus one worked case study. The models are illustrative and have not been validated against field data.** The sections below say exactly what is modelled, what is assumed, and what is missing.

The idea came from reading *An Introduction to Well Integrity*: a well is network-like, with barrier elements, components and leak paths, where degradation in one place can load or break something somewhere else. Here, components are objects that are assembled into a well and coupled through shared pressures.

## Case study: packer seal loss

[`notebooks/01_packer_seal_loss.ipynb`](notebooks/01_packer_seal_loss.ipynb) models the chain

> packer seal loss → leak into the A-annulus → sustained annulus pressure → casing burst utilisation → casing wall loss

and compares it with a healthy-packer reference. It also shows how much of the result is assumption (the sensitivity section) and checks the timestep error.

What is physically modelled:

| Piece | Model |
|---|---|
| Packer leak | `q = C (p_tubing − p_annulus)`, `C = C_max (1 − s)^n`, `s` = seal integrity |
| Annulus | closed compressible volume, `dp/dt = (K/V) q`, solved exactly per step; wellhead pressure = bottom pressure − ρgH |
| Casing load | burst utilisation = net internal pressure / API 5C3 internal-yield pressure at the *current* wall (the 9 5/8 in 47 lb/ft L80 rating reproduces the published 6870 psi, and this is unit-tested) |
| Barrier logic | an envelope fails if any member fails (series system) |

What is **assumed**, not derived or calibrated:

- the leak shape (`C_max`, `n`) and the prescribed linear seal loss;
- the baseline corrosion rate and the **stress coupling** `rate = r0 (1 + α u^m)`. The "accelerated wall loss" in the case study is *entirely* this coupling; with `α = 0` seal loss changes pressures but not wall loss;
- tubing pressure, annulus fluid properties, depths, equipment ratings.

What is **not modelled**: thermal expansion of annulus fluid, bleed-down through the annulus valve, gas in the annulus, collapse and axial loads, back-up load from cement and formation, packer failure driven by load or temperature, any pressure physics in the surface and reservoir segments (they currently see a zero-net-load placeholder).

## Install and run

```bash
pip install -e .            # library only (no dependencies)
pip install -e ".[notebooks,dev]"
python -m unittest discover -s tests     # or: pytest
jupyter lab notebooks/01_packer_seal_loss.ipynb
```

If you remove the old single-file `WellTwin.py` (this package replaces it), do so with `git rm WellTwin.py`: on case-insensitive filesystems it would otherwise shadow the `welltwin` package.

## Quick start

```python
from welltwin import DigitalTwin, WellConditions
from welltwin.examples import build_example_well
from welltwin.units import DAY, MPA, YEAR

twin = DigitalTwin(build_example_well(packer_life_years=10))
twin.run(WellConditions(tubing_pressure=45 * MPA), duration=15 * YEAR, dt=1 * DAY)

print(twin.barrier_status())     # {'Primary envelope': True, 'Secondary envelope': False}
history = twin.history_table()   # {"A-annulus.top_pressure": [...], ...}
```

## Design

```
welltwin/
  core.py          Environment, ComponentState, Component base class, degradation interface
  components.py    Tubular (Casing, Tubing), Cement, Formation, Packer, valves, seals, Annulus
  degradation.py   ConstantRateLoss, StressEnhancedWallLoss
  well.py          WellConditions, segments, BarrierEnvelope, Well
  twin.py          DigitalTwin: stepping, history, status queries
  examples.py      build_example_well(): the illustrative well used in the case study
  units.py         SI conversion constants
```

- **Units are SI throughout** (Pa gauge, m, s, K). Use `welltwin.units` to convert in.
- **Components own their state and failure rule.** `failure_condition(environment)` decides what "failed" means; `observe(environment)` refreshes derived quantities such as loads.
- **Segments own the coupling.** A segment decides which environment each component sees. `CasingSegment` couples packer, annulus, tubing and casing; the other segments use a neutral placeholder until they get their own physics.
- **Degradation models are plug-ins.** Anything with `step(state, environment, dt) -> new_state` can be attached with `component.add_degradation_model(...)`.
- Timestepping is first order. The case-study notebook reports the measured error versus step size.

## Roadmap

1. Annulus bleed-down and thermal expansion, so interventions can be modelled (how often to bleed, and what it does to casing load).
2. Calibrate packer leak behaviour against leak-test or annulus-pressure build-up data.
3. Replace the stress-coupled wall loss with a data-backed corrosion mechanism.
4. Barrier-path logic instead of the any-failure rule.
5. Collapse and axial loads for tubulars; attach flow solvers to components.
