import math
import unittest

from slicer_sweep.gcode_stats import mm_to_grams, parse_feature_lengths
from slicer_sweep.sliced import hms_to_seconds


class ParseFeatureLengthsTest(unittest.TestCase):
    def test_relative_extrusion_per_feature(self):
        g = """M83
; FEATURE: Outer wall
G1 X1 Y1 E.5
G1 X2 E0.25 ; comment
; FEATURE: Bridge
G3 X3 Y3 I1 J1 E1.5
""".splitlines()
        u = parse_feature_lengths(g, aliases={})
        self.assertAlmostEqual(u.length_mm["Outer wall"], 0.75)
        self.assertAlmostEqual(u.length_mm["Bridge"], 1.5)

    def test_retract_unretract_and_pure_e_moves_are_ignored(self):
        g = """M83
; FEATURE: Sparse infill
G1 E-0.8 F1800
G1 E0.8
G1 X5 Y5 F3000
G1 X6 Y6 E2
""".splitlines()
        u = parse_feature_lengths(g, aliases={})
        self.assertEqual(u.length_mm, {"Sparse infill": 2.0})

    def test_absolute_extrusion_with_g92(self):
        g = """M82
G92 E0
G1 E50 F200
G92 E0
G1 X10 E5
G1 X20 E7
G92 E0
G1 X30 E1
""".splitlines()
        u = parse_feature_lengths(g, aliases={})
        self.assertAlmostEqual(u.total_mm, 8.0)

    def test_gui_alias_merges_floating_vertical_shell(self):
        g = """M83
; FEATURE: Floating vertical shell
G1 X1 E1
; FEATURE: Internal solid infill
G1 X2 E2
""".splitlines()
        u = parse_feature_lengths(g)
        self.assertEqual(u.length_mm, {"Internal solid infill": 3.0})


class ConversionTest(unittest.TestCase):
    def test_matches_gui_reference(self):
        # Task reference: 39.73 m of 1.75 mm filament at 1.27 g/cm3 == 121.36 g
        self.assertAlmostEqual(mm_to_grams(39730, 1.75, 1.27), 121.36, delta=0.02)

    def test_formula(self):
        self.assertAlmostEqual(mm_to_grams(1000, 2.0, 1.0), math.pi)

    def test_hms(self):
        self.assertEqual(hms_to_seconds("4h 10m 23s"), 15023)
        self.assertEqual(hms_to_seconds("1d 2h"), 93600)


if __name__ == "__main__":
    unittest.main()
