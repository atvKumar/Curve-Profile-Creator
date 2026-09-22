import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FakeObject(dict):
    def __init__(self, values=None, **attributes):
        super().__init__(values or {})
        self.type = attributes.pop("type", "CURVE")
        self.scale = attributes.pop("scale", (1.0, 1.0, 1.0))
        for name, value in attributes.items():
            setattr(self, name, value)


def basic_component():
    return FakeObject(
        {
            "cpc_part": True,
            "cpc_parametric": True,
            "cpc_primitive_id": "LINE",
        },
        cpc_part_rotation=0.0,
        cpc_param_width=0.2,
        cpc_param_height=0.1,
        cpc_param_arc_depth=0.025,
        cpc_param_shape_mode="CIRCLE",
        cpc_param_bias=0.5,
        cpc_param_fullness=1.0,
        cpc_param_concave_fullness=1.0,
        cpc_param_convex_fullness=1.0,
        cpc_param_arc_construction_mode="FULLNESS",
    )


def packed_child():
    return FakeObject(
        {
            "cpc_part": True,
            "cpc_parametric": True,
            "cpc_primitive_id": "LINE",
            "cpc_arch_instance_id": "packed-1",
        },
        cpc_part_rotation=0.0,
        cpc_param_width=0.2,
    )


def packed_controller():
    return FakeObject(
        {"cpc_arch_component_id": "V_GROOVE"},
        cpc_arch_width=0.4,
        cpc_arch_height=0.15,
    )


def _load_viewport_semantics():
    package_name = "cpc_viewport_semantics_under_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT)]
    sys.modules[package_name] = package

    architectural_components = types.ModuleType(f"{package_name}.architectural_components")
    architectural_components.controller_for = lambda _obj: None
    architectural_components.controller_parameters = lambda _controller: {}
    architectural_components.instance_parts = lambda _controller: []
    architectural_components.apply_parameters = lambda _controller, _params, _context: True

    architectural_recipes = types.ModuleType(f"{package_name}.architectural_recipes")
    architectural_recipes.scale_length_parameters = lambda _component_id, params, _factor: dict(params)

    primitives = types.ModuleType(f"{package_name}.primitives")
    primitives.update_object_geometry = lambda *_args, **_kwargs: None

    profile_transforms = types.ModuleType(f"{package_name}.profile_transforms")
    profile_transforms.profile_placement_state = lambda _obj: {
        "rotation": 0.0,
        "uniform_scale": 1.0,
    }

    properties = types.ModuleType(f"{package_name}.properties")
    properties.set_profile_placement_state = lambda *_args, **_kwargs: None

    stubs = {
        "architectural_components": architectural_components,
        "architectural_recipes": architectural_recipes,
        "primitives": primitives,
        "profile_transforms": profile_transforms,
        "properties": properties,
    }
    for name, module in stubs.items():
        sys.modules[f"{package_name}.{name}"] = module
        setattr(package, name, module)

    spec = importlib.util.spec_from_file_location(
        f"{package_name}.viewport_semantics",
        ROOT / "viewport_semantics.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, stubs


viewport_semantics, _STUBS = _load_viewport_semantics()
architectural_components = _STUBS["architectural_components"]
profile_transforms = _STUBS["profile_transforms"]
properties = _STUBS["properties"]


class ViewportSemanticFieldTests(unittest.TestCase):
    def setUp(self):
        architectural_components.controller_for = lambda _obj: None
        architectural_components.controller_parameters = lambda _controller: {}
        architectural_components.instance_parts = lambda _controller: []
        architectural_components.apply_parameters = (
            lambda _controller, _params, _context: True
        )
        profile_transforms.profile_placement_state = lambda _obj: {
            "rotation": 0.0,
            "uniform_scale": 1.0,
        }
        profile_transforms.capture_profile_resize_state = (
            lambda state, _scale: dict(state)
        )
        profile_transforms.resolve_profile_semantic_field = (
            lambda state, field_id, value: {
                **state,
                "rotation" if field_id == "profile_rotation" else "uniform_scale": value,
            }
        )
        properties.set_profile_placement_state = lambda *_args, **_kwargs: None

    @staticmethod
    def _profile_context(profile):
        settings = types.SimpleNamespace(active_profile=profile)
        context = types.SimpleNamespace(
            scene=types.SimpleNamespace(cpc_settings=settings)
        )
        return context, settings

    def test_component_exposes_rotation_size_then_dimensions(self):
        obj = FakeObject(
            {
                "cpc_part": True,
                "cpc_parametric": True,
                "cpc_primitive_id": "LINE",
            },
            cpc_part_rotation=math.radians(12.0),
            cpc_param_width=0.25,
        )

        fields = viewport_semantics.fields_for(obj)

        self.assertEqual(
            [field.field_id for field in fields],
            ["part_rotation", "part_size", "length"],
        )
        self.assertEqual(
            [field.kind for field in fields],
            ["ANGLE", "RESIZE_ACTION", "LENGTH"],
        )
        self.assertAlmostEqual(fields[1].value, 1.0)

    def test_profile_exposes_canonical_rotation_and_uniform_scale(self):
        obj = FakeObject({"cpc_profile": True})
        profile_transforms.profile_placement_state = lambda _obj: {
            "rotation": math.radians(-22.5),
            "uniform_scale": 1.75,
        }

        fields = viewport_semantics.fields_for(obj)

        self.assertEqual(
            [field.field_id for field in fields],
            ["profile_rotation", "profile_uniform_scale"],
        )
        self.assertAlmostEqual(fields[0].value, math.radians(-22.5))
        self.assertAlmostEqual(fields[1].value, 1.75)

    def test_formatting_distinguishes_angle_factor_and_length(self):
        angle = viewport_semantics.SemanticField(
            "r", "Rotation", None, "", kind="ANGLE", value_override=math.pi / 4
        )
        factor = viewport_semantics.SemanticField(
            "s", "Size", None, "", kind="FACTOR", value_override=1.25
        )

        self.assertEqual(viewport_semantics.format_field_value(None, angle), "45.00°")
        self.assertEqual(viewport_semantics.format_field_value(None, factor), "1.250×")
        self.assertEqual(
            viewport_semantics.format_field_value(None, factor, value=2.5),
            "2.500×",
        )

    def test_length_scrub_resolves_from_fixed_baseline_with_shift_fine_motion(self):
        normal = viewport_semantics.resolve_scrub_value(
            "LENGTH", 0.2, 10.0, shift=False, ctrl=False
        )
        fine = viewport_semantics.resolve_scrub_value(
            "LENGTH", 0.2, 10.0, shift=True, ctrl=False
        )

        self.assertAlmostEqual(normal, 0.2 * math.exp(0.1))
        self.assertAlmostEqual(fine, 0.2 * math.exp(0.01))

    def test_angle_scrub_applies_snapped_delta_to_absolute_start_value(self):
        total_dx = math.radians(17.4) / 0.005

        value = viewport_semantics.resolve_scrub_value(
            "ANGLE",
            0.5,
            total_dx,
            shift=False,
            ctrl=True,
            rotation_snap_radians=math.radians(15.0),
        )

        self.assertAlmostEqual(value, 0.5 + math.radians(15.0))

    def test_factor_and_resize_action_use_different_absolute_baselines(self):
        total_dx = math.log(1.16) / 0.005

        factor = viewport_semantics.resolve_scrub_value(
            "FACTOR", 2.0, total_dx, shift=False, ctrl=True
        )
        resize_action = viewport_semantics.resolve_scrub_value(
            "RESIZE_ACTION", 1.0, total_dx, shift=False, ctrl=True
        )

        self.assertAlmostEqual(factor, 2.4)
        self.assertAlmostEqual(resize_action, 1.2)

    def test_component_rotation_write_is_authoritative(self):
        obj = FakeObject(
            {
                "cpc_part": True,
                "cpc_parametric": True,
                "cpc_primitive_id": "LINE",
            },
            cpc_part_rotation=0.0,
            cpc_param_width=0.2,
        )

        viewport_semantics.apply_value(obj, "part_rotation", math.radians(31.0))

        self.assertAlmostEqual(obj.cpc_part_rotation, math.radians(31.0))

    def test_packed_child_dimensions_are_owned_by_the_controller(self):
        child = packed_child()
        controller = packed_controller()
        architectural_components.controller_for = lambda _obj: controller

        fields = viewport_semantics.fields_for(child)

        dimensional = [field for field in fields if field.kind == "LENGTH"]
        self.assertTrue(dimensional)
        self.assertTrue(all(field.owner is controller for field in dimensional))

    def test_profile_rotation_write_uses_canonical_placement_setter(self):
        profile = FakeObject({"cpc_profile": True})
        context, settings = self._profile_context(profile)
        calls = []
        properties.set_profile_placement_state = (
            lambda got_settings, got_context, got_profile, **changes: calls.append(
                (got_settings, got_context, got_profile, changes)
            )
        )

        viewport_semantics.apply_value(
            profile, "profile_rotation", math.radians(17.0), context
        )

        self.assertEqual(
            calls,
            [(settings, context, profile, {"rotation": math.radians(17.0)})],
        )

    def test_profile_uniform_scale_write_uses_canonical_placement_setter(self):
        profile = FakeObject({"cpc_profile": True})
        context, settings = self._profile_context(profile)
        calls = []
        properties.set_profile_placement_state = (
            lambda got_settings, got_context, got_profile, **changes: calls.append(
                (got_settings, got_context, got_profile, changes)
            )
        )

        viewport_semantics.apply_value(
            profile, "profile_uniform_scale", 1.375, context
        )

        self.assertEqual(
            calls,
            [(settings, context, profile, {"uniform_scale": 1.375})],
        )

    def test_profile_uniform_scale_rejects_non_positive_before_setter(self):
        profile = FakeObject({"cpc_profile": True})
        context, _settings = self._profile_context(profile)
        calls = []
        properties.set_profile_placement_state = (
            lambda *_args, **_kwargs: calls.append((_args, _kwargs))
        )

        with self.assertRaisesRegex(ValueError, "greater than zero"):
            viewport_semantics.apply_value(
                profile, "profile_uniform_scale", 0.0, context
            )

        self.assertEqual(calls, [])

    def test_component_size_capture_uses_existing_uniform_resize_state(self):
        component = basic_component()

        state = viewport_semantics.capture_edit_state(component, "part_size")

        self.assertEqual(state["kind"], "COMPONENT_SIZE")
        self.assertIn("resize_state", state)
        self.assertEqual(state["resize_state"]["width"], 0.2)

    def test_component_size_capture_rejects_non_neutral_object_scale(self):
        component = basic_component()
        component.scale = (1.5, 1.5, 1.5)

        with self.assertRaisesRegex(ValueError, "Object Scale"):
            viewport_semantics.capture_edit_state(component, "part_size")

    def test_component_size_apply_keeps_every_packed_part_scale_neutral(self):
        child = packed_child()
        controller = packed_controller()
        sibling = packed_child()
        parts = [child, sibling]
        architectural_components.controller_for = lambda _obj: controller
        architectural_components.instance_parts = lambda _controller: parts

        def apply_parameters(_controller, _params, _context):
            for part in parts:
                part.scale = (1.25, 1.25, 1.25)
            return True

        architectural_components.apply_parameters = apply_parameters
        context, _settings = self._profile_context(None)
        state = viewport_semantics.capture_edit_state(child, "part_size")

        viewport_semantics.apply_edit_value(
            child, "part_size", 1.25, state, context
        )

        self.assertEqual(
            [tuple(part.scale) for part in viewport_semantics.uniform_resize_scope(child)],
            [(1.0, 1.0, 1.0)] * len(parts),
        )

    def test_component_rotation_restore_returns_exact_angle(self):
        component = basic_component()
        component.cpc_part_rotation = math.radians(11.0)
        state = viewport_semantics.capture_edit_state(component, "part_rotation")
        component.cpc_part_rotation = 2.0

        viewport_semantics.restore_edit_state(component, "part_rotation", state)

        self.assertEqual(component.cpc_part_rotation, state["value"])

    def test_profile_capture_rejects_non_uniform_raw_object_scale(self):
        profile = FakeObject({"cpc_profile": True}, scale=(1.0, 2.0, 1.0))

        def reject_non_uniform(_state, scale):
            if len(set(scale)) != 1:
                raise ValueError("Object Scale must be uniform")
            return dict(_state)

        profile_transforms.capture_profile_resize_state = reject_non_uniform

        with self.assertRaisesRegex(ValueError, "uniform"):
            viewport_semantics.capture_edit_state(
                profile, "profile_uniform_scale"
            )

    def test_profile_restore_returns_placement_and_raw_scale_exactly(self):
        original_placement = {
            "offset_x": 0.25,
            "offset_y": -0.5,
            "rotation": 0.75,
            "flip_x": True,
            "flip_y": False,
            "uniform_scale": 2.0,
        }
        profile = FakeObject(
            {"cpc_profile": True},
            scale=(1.25, 1.25, 1.25),
            placement=dict(original_placement),
        )
        context, _settings = self._profile_context(profile)
        profile_transforms.profile_placement_state = lambda obj: dict(obj.placement)
        profile_transforms.capture_profile_resize_state = (
            lambda state, scale: {
                **state,
                "offset_x": state["offset_x"] * scale[0],
                "offset_y": state["offset_y"] * scale[0],
                "uniform_scale": state["uniform_scale"] * scale[0],
            }
        )
        setter_scales = []

        def set_placement(_settings, _context, got_profile, state=None, **changes):
            setter_scales.append(tuple(got_profile.scale))
            got_profile.placement = {**(state or got_profile.placement), **changes}
            return dict(got_profile.placement)

        properties.set_profile_placement_state = set_placement
        state = viewport_semantics.capture_edit_state(
            profile, "profile_uniform_scale"
        )
        viewport_semantics.apply_edit_value(
            profile, "profile_uniform_scale", 3.0, state, context
        )
        self.assertEqual(setter_scales[0], (1.0, 1.0, 1.0))
        self.assertEqual(tuple(profile.scale), (1.0, 1.0, 1.0))

        viewport_semantics.restore_edit_state(
            profile, "profile_uniform_scale", state, context
        )

        self.assertEqual(
            profile_transforms.profile_placement_state(profile),
            state["original_placement"],
        )
        self.assertEqual(tuple(profile.scale), state["original_scale"])


if __name__ == "__main__":
    unittest.main()
