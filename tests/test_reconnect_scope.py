import importlib.util
from pathlib import Path
import sys
import types
import unittest

import endpoint_reconnect


ROOT = Path(__file__).resolve().parents[1]


class FakeObject(dict):
    def __init__(self, name, *, object_type="CURVE", part=True, parametric=True, preview=False):
        super().__init__()
        self.name = name
        self.type = object_type
        if part:
            self["cpc_part"] = True
        if parametric:
            self["cpc_parametric"] = True
        if preview:
            self["cpc_preview"] = True


def _load_junctions():
    package_name = "cpc_junctions_scope_under_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT)]
    sys.modules[package_name] = package

    bpy = types.ModuleType("bpy")
    bpy.data = types.SimpleNamespace(collections=None)
    sys.modules.setdefault("bpy", bpy)

    mathutils = types.ModuleType("mathutils")
    mathutils.Vector = type("Vector", (), {})
    sys.modules.setdefault("mathutils", mathutils)

    library = types.ModuleType(f"{package_name}.library")
    library.object_endpoint_world = lambda obj, endpoint_index: (0.0, 0.0, 0.0)
    sys.modules[f"{package_name}.library"] = library
    setattr(package, "library", library)

    sys.modules[f"{package_name}.endpoint_reconnect"] = endpoint_reconnect
    setattr(package, "endpoint_reconnect", endpoint_reconnect)

    spec = importlib.util.spec_from_file_location(
        f"{package_name}.junctions",
        ROOT / "junctions.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


junctions = _load_junctions()


def eligible_part(name):
    return FakeObject(name)


def preview_part():
    return FakeObject("preview", preview=True)


def static_part():
    return FakeObject("static", parametric=False)


def mesh_object():
    return FakeObject("mesh", object_type="MESH")


class ReconnectScopeTests(unittest.TestCase):
    def test_active_session_wins_over_selection(self):
        active = [eligible_part("a"), eligible_part("b")]
        selected = [eligible_part("outside")]
        self.assertEqual(
            junctions.choose_reconnect_candidates(active, selected), active
        )

    def test_selection_is_used_without_active_session(self):
        selected = [eligible_part("a"), eligible_part("b")]
        self.assertEqual(
            junctions.choose_reconnect_candidates([], selected), selected
        )

    def test_ineligible_objects_are_filtered(self):
        selected = [preview_part(), static_part(), mesh_object(), eligible_part("keep")]
        self.assertEqual(
            junctions.choose_reconnect_candidates([], selected), [selected[-1]]
        )


if __name__ == "__main__":
    unittest.main()
