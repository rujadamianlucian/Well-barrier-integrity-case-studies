"""Tests for welltwin. Plain ``unittest``, so ``python -m unittest`` and ``pytest`` both run them."""

import unittest
from dataclasses import replace

from welltwin import DHSV, Annulus, Casing, DigitalTwin, Well, WellConditions
from welltwin.examples import build_example_well
from welltwin.units import DAY, INCH, MPA, PSI, YEAR

CONDITIONS = WellConditions(tubing_pressure=45 * MPA)


def simulate(days, dt_days=1.0, **well_kwargs):
    twin = DigitalTwin(build_example_well(**well_kwargs))
    twin.run(CONDITIONS, duration=days * DAY, dt=dt_days * DAY)
    return twin


def final(twin, key):
    return twin.history_table()[key][-1]


class TestTubular(unittest.TestCase):
    def test_burst_rating_matches_api_5c3_published_value(self):
        # 9 5/8 in, 47 lb/ft, L80: API 5C3 internal yield pressure is 6870 psi.
        casing = Casing(
            "c",
            outer_diameter=9.625 * INCH,
            wall_thickness=0.472 * INCH,
            yield_strength=80_000 * PSI,
        )
        self.assertAlmostEqual(casing.burst_rating / PSI, 6870, delta=0.01 * 6870)

    def test_rejects_impossible_geometry(self):
        with self.assertRaises(ValueError):
            Casing("c", outer_diameter=0.2, wall_thickness=0.15, yield_strength=5e8)


class TestAnnulus(unittest.TestCase):
    def make(self):
        return Annulus("a", volume=80.0, height=3000.0)

    def test_closed_annulus_does_not_change(self):
        annulus = self.make()
        p0 = annulus.pressure
        annulus.relax_towards(45 * MPA, conductance=0.0, dt=100 * YEAR)
        self.assertEqual(annulus.pressure, p0)

    def test_relaxation_is_independent_of_step_size(self):
        one, many = self.make(), self.make()
        one.relax_towards(45 * MPA, 1e-13, 10 * DAY)
        for _ in range(10):
            many.relax_towards(45 * MPA, 1e-13, 1 * DAY)
        self.assertAlmostEqual(one.pressure, many.pressure, delta=1e-3)  # Pa

    def test_pressure_never_overshoots_the_source(self):
        annulus = self.make()
        annulus.relax_towards(45 * MPA, conductance=1.0, dt=1 * YEAR)  # absurdly stiff
        self.assertLessEqual(annulus.pressure, 45 * MPA)
        self.assertAlmostEqual(annulus.pressure, 45 * MPA, delta=1.0)

    def test_leaked_volume_matches_compressibility(self):
        annulus = self.make()
        p0 = annulus.pressure
        annulus.relax_towards(45 * MPA, 1e-13, 30 * DAY)
        expected = annulus.volume / annulus.bulk_modulus * (annulus.pressure - p0)
        self.assertAlmostEqual(annulus.state.variables["leaked_volume"], expected, places=12)


class TestPackerSealLossCase(unittest.TestCase):
    def test_healthy_packer_keeps_annulus_closed_and_wall_loss_at_baseline(self):
        twin = simulate(15 * 365, packer_life_years=None)
        well = twin.well
        self.assertTrue(
            all(abs(p) < 1.0 for p in twin.history_table()["A-annulus.top_pressure"])
        )
        self.assertEqual(twin.failed_components(), [])
        expected_wall = (
            well.casing.production_casing.initial_wall_thickness
            - 0.1e-3 / YEAR * twin.time
        )
        self.assertAlmostEqual(well.casing.production_casing.wall_thickness, expected_wall, places=9)

    def test_seal_loss_raises_annulus_pressure_monotonically_towards_tubing_pressure(self):
        twin = simulate(15 * 365)
        pressure = twin.history_table()["A-annulus.pressure"]
        self.assertTrue(all(b >= a - 1e-6 for a, b in zip(pressure, pressure[1:])))
        self.assertLessEqual(max(pressure), 45 * MPA + 1.0)
        hydrostatic = twin.well.casing.annulus.hydrostatic_pressure
        self.assertAlmostEqual(final(twin, "A-annulus.top_pressure"), 45 * MPA - hydrostatic, delta=1e3)

    def test_stress_coupling_accelerates_wall_loss(self):
        plain = simulate(15 * 365, stress_factor=0.0)
        coupled = simulate(15 * 365, stress_factor=5.0)
        key = "Production casing.wall_thickness"
        self.assertLess(final(coupled, key), final(plain, key) - 1e-5)

    def test_stress_coupling_has_no_effect_when_unloaded(self):
        plain = simulate(15 * 365, packer_life_years=None, stress_factor=0.0)
        coupled = simulate(15 * 365, packer_life_years=None, stress_factor=10.0)
        key = "Production casing.wall_thickness"
        self.assertAlmostEqual(final(plain, key), final(coupled, key), places=12)

    def test_primary_envelope_fails_with_the_packer_and_secondary_does_not(self):
        early = simulate(5 * 365)
        late = simulate(11 * 365)
        self.assertEqual(early.barrier_status(), {"Primary envelope": False, "Secondary envelope": False})
        self.assertEqual(late.barrier_status(), {"Primary envelope": True, "Secondary envelope": False})
        self.assertEqual([c.name for c in late.failed_components()], ["Packer"])

    def test_timestep_error_shrinks_and_is_small_at_one_day(self):
        # Day 540 is inside the pressure build-up, where the splitting error is visible.
        key = "A-annulus.top_pressure"
        reference = final(simulate(540, dt_days=0.5), key)

        def error(dt_days):
            return abs(final(simulate(540, dt_days=dt_days), key) - reference) / reference

        self.assertLess(error(1.0), 0.005)
        self.assertGreater(error(10.0), error(5.0))
        self.assertGreater(error(5.0), error(1.0))

    def test_wall_loss_is_insensitive_to_timestep(self):
        key = "Production casing.wall_thickness"
        fine, coarse = final(simulate(3000, dt_days=1.0), key), final(simulate(3000, dt_days=10.0), key)
        self.assertLess(abs(fine - coarse) / fine, 0.001)


class TestWell(unittest.TestCase):
    def test_duplicate_component_names_are_rejected(self):
        well = build_example_well()
        clash = replace(well.reservoir, dhsv=DHSV("Packer", pressure_rating=1e7))
        with self.assertRaises(ValueError):
            Well(surface=well.surface, casing=well.casing, reservoir=clash)

    def test_lookup_by_name(self):
        well = build_example_well()
        self.assertIs(well.get("Packer"), well.casing.packer)
        with self.assertRaises(KeyError):
            well.get("nope")


if __name__ == "__main__":
    unittest.main()
