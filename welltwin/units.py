"""Unit constants.

The library works in SI throughout: pressures in Pa (gauge), lengths in m,
time in s, temperature in K. Multiply by these constants to convert *into* SI,
e.g. ``45 * MPA`` or ``10 * YEAR``.
"""

G = 9.80665          # gravitational acceleration, m/s^2

DAY = 86_400.0       # s
YEAR = 365.25 * DAY  # s

KPA = 1e3            # Pa
MPA = 1e6            # Pa
PSI = 6_894.757293168  # Pa

MM = 1e-3            # m
INCH = 0.0254        # m
