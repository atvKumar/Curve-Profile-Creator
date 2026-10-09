import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _load_profile_presets():
    spec = importlib.util.spec_from_file_location(
        "cpc_profile_presets_under_test",
        ROOT / "profile_presets.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


profile_presets = _load_profile_presets()


def _matrix():
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


class CustomBezierPresetValidationTests(unittest.TestCase):
    def _document(self):
        return {
            "format": profile_presets.PRESET_FORMAT,
            "format_version": profile_presets.PRESET_FORMAT_VERSION,
            "id": "preset-test",
            "name": "Mixed CPC Bezier",
            "profile_type": profile_presets.PROFILE_TYPE_PARAMETRIC,
            "geometry": {"splines": [{"type": "BEZIER", "points": []}]},
            "recipe": {
                "schema_version": profile_presets.MIN_PARAMETRIC_RECIPE_SCHEMA,
                "transform_version": 1,
                "frame_policy": "ANCHOR_WORLD_AXES",
                "records": [
                    {
                        "id": "line-1",
                        "primitive_id": "LINE",
                        "matrix_profile": _matrix(),
                    },
                    {
                        "id": "custom-1",
                        "primitive_id": "",
                        "component_type": "CUSTOM_BEZIER",
                        "matrix_profile": _matrix(),
                        "custom_bezier": {
                            "version": 1,
                            "spline_type": "BEZIER",
                            "cyclic": False,
                            "points": [
                                {
                                    "co": [0.0, 0.0, 0.0],
                                    "handle_left": [-0.1, 0.0, 0.0],
                                    "handle_right": [0.1, 0.0, 0.0],
                                    "handle_left_type": "FREE",
                                    "handle_right_type": "FREE",
                                },
                                {
                                    "co": [1.0, 0.5, 0.0],
                                    "handle_left": [0.9, 0.4, 0.0],
                                    "handle_right": [1.1, 0.6, 0.0],
                                    "handle_left_type": "ALIGNED",
                                    "handle_right_type": "ALIGNED",
                                },
                            ],
                        },
                    },
                ],
            },
        }

    def test_custom_bezier_record_is_valid_parametric_recipe_member(self):
        validated = profile_presets.validate_preset_document(self._document())
        self.assertEqual(validated["profile_type"], profile_presets.PROFILE_TYPE_PARAMETRIC)
        self.assertEqual(validated["recipe"]["records"][1]["component_type"], "CUSTOM_BEZIER")

    def test_custom_bezier_requires_payload(self):
        document = self._document()
        document["recipe"]["records"][1].pop("custom_bezier")
        with self.assertRaises(profile_presets.PresetFormatError):
            profile_presets.validate_preset_document(document)

    def test_ordinary_parametric_record_still_requires_primitive_id(self):
        document = self._document()
        document["recipe"]["records"][0]["primitive_id"] = ""
        with self.assertRaises(profile_presets.PresetFormatError):
            profile_presets.validate_preset_document(document)


if __name__ == "__main__":
    unittest.main()
