# Well Barrier Integrity Case Studies

A small Python-based project exploring **well integrity, barrier degradation, and predictive maintenance** through simplified digital-twin style models.

After looking through several well barrier schematics and trying to trace different possible leak paths, I was struck by how quickly the system becomes difficult to represent mathematically as a whole. Rather than implementing one particular model for one well, I decided to build the project around a modular, object-oriented “Lego-like” structure. Here each barrier element has its own state, properties, and interactions with neighbouring components. The idea is to first establish a flexible system architecture that can track degradation and barrier states, and then progressively replace simplified component models with more rigorous finite-element, finite-volume, or other physics-based solvers where needed.

As I keep working on this project, I want to be able to:
- Know the purpose of some of the central well barrier elements 
- model degradation of key components over time,
- couple neighbouring components through pressure, temperature, and barrier-state interactions,
- estimate hidden integrity states from observations,
- and forecaste future degradation or barrier failure risk.

The intended use is educational and exploratory rather than field deployment.

## About Scripts and notebooks:

WellTwin.py is the core of this repository. It contains the basic object-oriented framework used to represent well segments, barrier elements, component states, and their interactions.
As the project develops, I plan to add notebooks that explore different degradation mechanisms and the types of failure they may lead to. These notebooks will be used as small numerical experiments for testing ideas such as corrosion, seal degradation, pressure-driven failure, barrier deterioration, and uncertainty in component condition.
If I come across sufficiently detailed real-world or publicly available data, I also plan to add dedicated case-study folders. The aim in those cases will be to build simple digital-twin style models, update component states from available measurements, and track how the estimated integrity of the well changes over time.

## Current status

The project is still in an early exploratory stage.

At the moment, `WellTwin.py` contains a basic framework for assembling wells from reusable components and tracking component states. The current models are intentionally simplified, with the focus placed on system structure, coupling, degradation modelling, and uncertainty rather than detailed field-scale physics.

Some of the first example models focus on:

- packer seal degradation,
- annulus pressure build-up,
- casing wall loss / corrosion,
- and simple barrier-state tracking.

## Repository structure

```text
Well-barrier-integrity-case-studies/
│
├── WellTwin.py
├── notebooks/
├── case_studies/
├── figures/
└── README.md
