import string
import unittest
from decimal import Decimal as D

from slicer_sweep.cli import summary
from slicer_sweep.i18n import MESSAGES, set_lang
from slicer_sweep.sweep import RunResult, best, density_list, fmt_num


class DensityListTest(unittest.TestCase):
    def test_list_with_decimals_and_percent(self):
        self.assertEqual(density_list("3, 10.5,11%"), [D("3"), D("10.5"), D("11")])

    def test_inclusive_range_without_float_drift(self):
        got = density_list(start="5", end="6", step="0.1")
        self.assertEqual(len(got), 11)
        self.assertEqual(got[-1], D("6.0"))

    def test_range_plus_list_deduplicates(self):
        self.assertEqual(density_list("10,20", "9", "11", "1"), [D(10), D(20), D(9), D(11)])

    def test_rejects_bad_input(self):
        for kwargs in ({"values": "abc"}, {"values": "120"},
                       {"start": "5", "end": "1", "step": "1"},
                       {"start": "1", "end": "5", "step": "0"}):
            with self.assertRaises(ValueError):
                density_list(**kwargs)

    def test_fmt_num(self):
        self.assertEqual(fmt_num(D("10.50")), "10.5")
        self.assertEqual(fmt_num(D("10")), "10")
        self.assertEqual(fmt_num(D("6.0")), "6")


def run(d, g, t, sparse=1.0, bridge=2.0):
    return RunResult(pattern="gyroid", density=D(d), total_g=g, total_time_s=t,
                     total_time=f"{t}s", features_g={"Sparse infill": sparse, "Bridge": bridge})


class BestTest(unittest.TestCase):
    def test_ties_and_errors(self):
        rs = [run(5, 110.0, 100), run(6, 101.001, 90), run(7, 100.999, 95),
              RunResult(pattern="gyroid", density=D(8), status="error", error="x")]
        self.assertEqual([fmt_num(r.density) for r in best(rs, "total_g")], ["6", "7"])
        self.assertEqual([fmt_num(r.density) for r in best(rs, "total_time_s")], ["6"])

    def tearDown(self):
        set_lang("zh-TW")

    def test_summary_marks_and_sum(self):
        set_lang("zh-TW")
        text = summary([run(5, 110.0, 100, 3.0, 4.5), run(6, 100.0, 90)])
        self.assertIn("7.50", text)          # sparse + bridge
        self.assertIn("★最少用料", text)
        self.assertIn("總用料最少：6%", text)

    def test_summary_english(self):
        set_lang("en")
        text = summary([run(5, 110.0, 100), run(6, 100.0, 90)])
        self.assertIn("Sparse+Bridge g", text)
        self.assertIn("★least filament", text)
        self.assertIn("Least filament: 6% (100.00 g, 90s)", text)
        self.assertNotRegex(text, r"[一-鿿]")


class MessagesTest(unittest.TestCase):
    def test_both_languages_use_the_same_placeholders(self):
        fields = lambda s: sorted(f for _, f, _, _ in string.Formatter().parse(s) if f)  # noqa: E731
        for key, (zh, en) in MESSAGES.items():
            self.assertEqual(fields(zh), fields(en), key)
            self.assertNotRegex(en, r"[一-鿿]", key)


if __name__ == "__main__":
    unittest.main()
