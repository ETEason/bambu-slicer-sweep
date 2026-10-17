import io
import unittest
import zipfile

from slicer_sweep.cli import override_warning
from slicer_sweep.i18n import set_lang, t
from slicer_sweep.sweep import object_overrides

MODEL_SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="2">
    <metadata key="name" value="Blade"/>
    <metadata key="sparse_infill_density" value="60%"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="Blade"/>
    </part>
  </object>
  <object id="4">
    <metadata key="name" value="Hinge"/>
    <part id="3" subtype="normal_part">
      <metadata key="name" value="Pin"/>
      <metadata key="sparse_infill_pattern" value="grid"/>
      <metadata key="wall_loops" value="4"/>
    </part>
  </object>
  <object id="6">
    <metadata key="name" value="Plain"/>
  </object>
  <object id="8">
    <metadata key="name" value="OtherPlate"/>
    <metadata key="sparse_infill_density" value="5%"/>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <model_instance><metadata key="object_id" value="2"/></model_instance>
    <model_instance><metadata key="object_id" value="4"/></model_instance>
    <model_instance><metadata key="object_id" value="6"/></model_instance>
  </plate>
  <plate>
    <metadata key="plater_id" value="2"/>
    <model_instance><metadata key="object_id" value="8"/></model_instance>
  </plate>
</config>
"""
KEYS = {"sparse_infill_density", "sparse_infill_pattern"}


def model(settings: str = MODEL_SETTINGS) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        if settings:
            z.writestr("Metadata/model_settings.config", settings)
    buf.seek(0)
    return buf


class ObjectOverridesTest(unittest.TestCase):
    def test_object_and_part_settings_on_the_plate(self):
        got = [(o.object_name, o.part_name, o.key, o.value) for o in object_overrides(model(), 1, KEYS)]
        self.assertEqual(got, [("Blade", None, "sparse_infill_density", "60%"),
                               ("Hinge", "Pin", "sparse_infill_pattern", "grid")])

    def test_other_plates_are_ignored(self):
        got = [o.object_name for o in object_overrides(model(), 2, KEYS)]
        self.assertEqual(got, ["OtherPlate"])

    def test_pinned_keys_are_checked_too(self):
        got = [o.key for o in object_overrides(model(), 1, KEYS | {"wall_loops"})]
        self.assertIn("wall_loops", got)

    def test_no_model_settings(self):
        self.assertEqual(object_overrides(model(""), 1, KEYS), [])

    def test_warning_text(self):
        set_lang("zh-TW")
        text = override_warning(object_overrides(model(), 1, KEYS))
        self.assertIn("Blade（物件 id 2）：sparse_infill_density = 60%", text)
        self.assertIn("Hinge（物件 id 4）的零件 Pin：sparse_infill_pattern = grid", text)
        self.assertIn("不進行切片", text)
        self.assertEqual(override_warning([]), "")


class TranslateTest(unittest.TestCase):
    def test_placeholder_named_key(self):
        # Regression: t()'s own parameter used to be called "key".
        set_lang("zh-TW")
        self.assertIn("wall_loops", t("set_reserved", key="wall_loops"))


if __name__ == "__main__":
    unittest.main()
