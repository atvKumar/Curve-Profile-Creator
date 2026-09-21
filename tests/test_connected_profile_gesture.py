import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FakeMatrix:
    def __init__(self, marker):
        self.marker = marker

    def copy(self):
        return FakeMatrix(self.marker)


class FakeObject:
    def __init__(self):
        self.type = 'CURVE'
        self.matrix_world = FakeMatrix("neutral")
        self._props = {"cpc_profile": True}

    def get(self, key, default=None):
        return self._props.get(key, default)

    def as_pointer(self):
        return 12345


def _load_connected_transforms():
    bpy = types.ModuleType("bpy")
    bpy.types = types.SimpleNamespace(Object=FakeObject)
    bpy.data = types.SimpleNamespace(collections={})
    bpy.context = types.SimpleNamespace(window_manager=None)

    handlers = types.ModuleType("bpy.app.handlers")
    handlers.persistent = lambda fn: fn
    handlers.depsgraph_update_post = []
    handlers.load_post = []
    app = types.ModuleType("bpy.app")
    app.handlers = handlers
    bpy.app = app
    sys.modules["bpy"] = bpy
    sys.modules["bpy.app"] = app
    sys.modules["bpy.app.handlers"] = handlers

    mathutils = types.ModuleType("mathutils")
    mathutils.Matrix = FakeMatrix
    mathutils.Vector = type("Vector", (), {})
    sys.modules["mathutils"] = mathutils

    package = types.ModuleType("cpc_connected_test")
    package.__path__ = [str(ROOT)]
    sys.modules["cpc_connected_test"] = package
    for name in ("junctions", "library", "profile_transforms"):
        sys.modules[f"cpc_connected_test.{name}"] = types.ModuleType(
            f"cpc_connected_test.{name}"
        )

    spec = importlib.util.spec_from_file_location(
        "cpc_connected_test.connected_transforms",
        ROOT / "connected_transforms.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


connected_transforms = _load_connected_transforms()


class ProfileGestureLifecycleTests(unittest.TestCase):
    def test_end_profile_transform_discards_stale_gesture_and_syncs_matrix(self):
        end_gesture = getattr(connected_transforms, "end_profile_transform", None)
        self.assertIsNotNone(
            end_gesture,
            "direct profile resize must end a stale native G/R gesture",
        )

        profile = FakeObject()
        key = connected_transforms._object_key(profile)
        connected_transforms._PROFILE_GESTURES[key] = {"matrix": FakeMatrix("stale")}
        connected_transforms._PROFILE_MATRIX_CACHE[key] = FakeMatrix("stale")

        end_gesture(profile)

        self.assertNotIn(key, connected_transforms._PROFILE_GESTURES)
        self.assertEqual(
            connected_transforms._PROFILE_MATRIX_CACHE[key].marker,
            "neutral",
        )


if __name__ == "__main__":
    unittest.main()
