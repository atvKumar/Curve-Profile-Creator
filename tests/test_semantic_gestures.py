import math
import unittest

import semantic_gestures


class SemanticGestureTests(unittest.TestCase):
    def test_shift_uses_one_tenth_rotation_motion_from_same_raw_baseline(self):
        raw = math.radians(37.0)
        normal = semantic_gestures.rotation_delta(
            raw, shift=False, ctrl=False, snap_radians=math.radians(15.0)
        )
        fine = semantic_gestures.rotation_delta(
            raw, shift=True, ctrl=False, snap_radians=math.radians(15.0)
        )
        self.assertAlmostEqual(fine, normal * 0.1)

    def test_ctrl_and_shift_ctrl_use_configured_rotation_steps(self):
        raw = math.radians(17.4)
        coarse = semantic_gestures.rotation_delta(
            raw, shift=False, ctrl=True, snap_radians=math.radians(15.0)
        )
        fine = semantic_gestures.rotation_delta(
            raw, shift=True, ctrl=True, snap_radians=math.radians(15.0)
        )
        self.assertAlmostEqual(coarse, math.radians(15.0))
        self.assertAlmostEqual(fine, math.radians(1.5))

    def test_ctrl_and_shift_ctrl_snap_size_factor(self):
        self.assertAlmostEqual(
            semantic_gestures.resize_factor(1.16, shift=False, ctrl=True), 1.2
        )
        self.assertAlmostEqual(
            semantic_gestures.resize_factor(1.16, shift=True, ctrl=True), 1.02
        )

    def test_modifier_toggles_recompute_from_raw_value(self):
        raw = 1.37
        first = semantic_gestures.resize_factor(raw, shift=False, ctrl=True)
        fine = semantic_gestures.resize_factor(raw, shift=True, ctrl=True)
        again = semantic_gestures.resize_factor(raw, shift=False, ctrl=True)
        self.assertEqual(first, again)
        self.assertNotEqual(first, fine)

    def test_typed_values_are_exact_and_finite(self):
        self.assertAlmostEqual(
            semantic_gestures.parse_angle_degrees("7.3"), math.radians(7.3)
        )
        self.assertAlmostEqual(semantic_gestures.parse_positive_factor("1.234"), 1.234)
        for value in ("0", "-1", "nan", "inf", "-"):
            with self.assertRaises(ValueError):
                semantic_gestures.parse_positive_factor(value)

    def test_typed_rotation_is_absolute_from_existing_value(self):
        start = math.radians(30.0)
        typed = semantic_gestures.rotation_target(
            start,
            typed_degrees="10",
        )
        dragged = semantic_gestures.rotation_target(
            start,
            delta=math.radians(5.0),
        )
        self.assertAlmostEqual(typed, math.radians(10.0))
        self.assertAlmostEqual(dragged, math.radians(35.0))

    def test_size_factor_never_reaches_zero_after_coarse_snap(self):
        self.assertEqual(
            semantic_gestures.resize_factor(0.01, shift=False, ctrl=True),
            semantic_gestures.MIN_FACTOR,
        )

    def test_negative_rotation_snaps_symmetrically(self):
        value = semantic_gestures.rotation_delta(
            math.radians(-17.4),
            shift=False,
            ctrl=True,
            snap_radians=math.radians(15.0),
        )
        self.assertAlmostEqual(value, math.radians(-15.0))


if __name__ == "__main__":
    unittest.main()
