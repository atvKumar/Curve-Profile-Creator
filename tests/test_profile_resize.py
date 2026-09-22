import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]


def _load_profile_transforms():
    mathutils = types.ModuleType("mathutils")
    mathutils.Matrix = type("Matrix", (), {})
    mathutils.Vector = type("Vector", (), {})
    sys.modules.setdefault("mathutils", mathutils)

    spec = importlib.util.spec_from_file_location(
        "cpc_profile_transforms_under_test",
        ROOT / "profile_transforms.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


profile_transforms = _load_profile_transforms()


class ProfileResizeGestureTests(unittest.TestCase):
    def setUp(self):
        self.capture = getattr(profile_transforms, "capture_profile_resize_state", None)
        self.apply = getattr(profile_transforms, "apply_profile_resize_factor", None)
        self.accepted_factor = getattr(profile_transforms, "accepted_profile_resize_factor", None)
        self.assertIsNotNone(
            self.capture,
            "committed-profile S needs a fixed semantic resize baseline",
        )
        self.assertIsNotNone(
            self.apply,
            "committed-profile S needs absolute factor resolution",
        )
        self.assertIsNotNone(
            self.accepted_factor,
            "committed-profile S must resolve immediate and numeric acceptance",
        )

    @staticmethod
    def _placement():
        return {
            "offset_x": 0.25,
            "offset_y": -0.5,
            "rotation": 0.75,
            "flip_x": True,
            "flip_y": False,
            "uniform_scale": 2.0,
        }

    def test_numeric_factor_multiplies_only_semantic_uniform_scale(self):
        baseline = self.capture(self._placement(), (1.0, 1.0, 1.0))
        result = self.apply(baseline, 1.5)

        self.assertTrue(math.isclose(result["uniform_scale"], 3.0))
        self.assertEqual(result["offset_x"], 0.25)
        self.assertEqual(result["offset_y"], -0.5)
        self.assertEqual(result["rotation"], 0.75)
        self.assertIs(result["flip_x"], True)
        self.assertIs(result["flip_y"], False)

    def test_existing_uniform_object_scale_is_absorbed_once(self):
        baseline = self.capture(self._placement(), (1.25, 1.25, 1.25))

        self.assertTrue(math.isclose(baseline["uniform_scale"], 2.5))
        self.assertTrue(math.isclose(baseline["offset_x"], 0.3125))
        self.assertTrue(math.isclose(baseline["offset_y"], -0.625))
        self.assertTrue(math.isclose(self.apply(baseline, 1.5)["uniform_scale"], 3.75))
        self.assertTrue(math.isclose(self.apply(baseline, 1.5)["uniform_scale"], 3.75))

        # Hand-derived 1D projection of ObjectScale @ Offset @ UniformScale.
        old_world_x = 1.25 * (0.25 + 2.0 * 0.4)
        new_world_x = baseline["offset_x"] + baseline["uniform_scale"] * 0.4
        self.assertTrue(math.isclose(old_world_x, 1.3125))
        self.assertTrue(math.isclose(new_world_x, 1.3125))

    def test_non_uniform_or_non_positive_object_scale_is_rejected(self):
        with self.assertRaises(profile_transforms.ProfileTransformError):
            self.capture(self._placement(), (1.0, 2.0, 1.0))
        with self.assertRaises(profile_transforms.ProfileTransformError):
            self.capture(self._placement(), (-1.0, -1.0, -1.0))

    def test_non_positive_gesture_factor_is_rejected(self):
        baseline = self.capture(self._placement(), (1.0, 1.0, 1.0))
        with self.assertRaises(profile_transforms.ProfileTransformError):
            self.apply(baseline, 0.0)

    def test_accept_without_numeric_input_uses_current_factor(self):
        self.assertTrue(math.isclose(self.accepted_factor("", 1.0), 1.0))
        self.assertTrue(math.isclose(self.accepted_factor("", 1.25), 1.25))

    def test_accept_numeric_input_rejects_invalid_or_non_positive_factor(self):
        self.assertTrue(math.isclose(self.accepted_factor("1.5", 1.0), 1.5))
        with self.assertRaises(profile_transforms.ProfileTransformError):
            self.accepted_factor("not-a-number", 1.0)
        with self.assertRaises(profile_transforms.ProfileTransformError):
            self.accepted_factor("0", 1.0)
        with self.assertRaises(profile_transforms.ProfileTransformError):
            self.accepted_factor("-", 1.0)

    def test_absolute_overlay_rotation_changes_only_rotation(self):
        original = self._placement()

        result = profile_transforms.resolve_profile_semantic_field(
            original, "profile_rotation", -1.25
        )

        self.assertEqual(result["rotation"], -1.25)
        self.assertEqual(result["uniform_scale"], original["uniform_scale"])
        self.assertEqual(result["offset_x"], original["offset_x"])
        self.assertEqual(original, self._placement())

    def test_absolute_overlay_uniform_scale_changes_only_scale(self):
        original = self._placement()

        result = profile_transforms.resolve_profile_semantic_field(
            original, "profile_uniform_scale", 0.375
        )

        self.assertEqual(result["uniform_scale"], 0.375)
        self.assertEqual(result["rotation"], original["rotation"])
        self.assertEqual(original, self._placement())

    def test_absolute_overlay_uniform_scale_rejects_non_positive_value(self):
        with self.assertRaises(profile_transforms.ProfileTransformError):
            profile_transforms.resolve_profile_semantic_field(
                self._placement(), "profile_uniform_scale", 0.0
            )

    def test_absolute_overlay_rejects_unknown_field(self):
        with self.assertRaises(profile_transforms.ProfileTransformError):
            profile_transforms.resolve_profile_semantic_field(
                self._placement(), "not_a_field", 1.0
            )


if __name__ == "__main__":
    unittest.main()
