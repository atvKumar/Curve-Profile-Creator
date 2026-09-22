import importlib.util
from pathlib import Path
import sys
import types
import unittest

import endpoint_reconnect


ROOT = Path(__file__).resolve().parents[1]


class FakeObject(dict):
    _next_pointer = 1

    def __init__(self, name, *, sequence, start, end):
        super().__init__(
            {
                "cpc_component_id": name,
                "cpc_seq": sequence,
                "cpc_part": True,
                "cpc_parametric": True,
            }
        )
        self.name = name
        self.type = "CURVE"
        self.positions = (tuple(start), tuple(end))
        self._pointer = FakeObject._next_pointer
        FakeObject._next_pointer += 1

    def as_pointer(self):
        return self._pointer


def _load_junctions():
    package_name = "cpc_junctions_under_test"
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
    library.object_endpoint_world = lambda obj, endpoint_index: obj.positions[
        int(endpoint_index)
    ]
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


def touching_pair_plus_remote():
    return (
        FakeObject("left", sequence=1, start=(0, 0, 0), end=(1, 0, 0)),
        FakeObject("right", sequence=2, start=(1, 0, 0), end=(2, 0, 0)),
        FakeObject("remote", sequence=3, start=(9, 0, 0), end=(10, 0, 0)),
    )


def set_host_record(obj, endpoint_index, host_component_id):
    junctions.set_hosted_record(
        obj,
        endpoint_index,
        {
            "host_component_id": host_component_id,
            "kind": "MIDPOINT",
            "fraction": 0.5,
        },
    )


class JunctionReconnectTests(unittest.TestCase):
    def test_reconnect_assigns_one_id_without_moving_coordinates(self):
        left = FakeObject(
            "left", sequence=1, start=(0, 0, 0), end=(1, 0, 0)
        )
        right = FakeObject(
            "right", sequence=2, start=(1, 0, 0), end=(2, 0, 0)
        )
        before = (left.positions, right.positions)

        stats = junctions.reconnect_touching_endpoints([left, right], 0.001)

        self.assertEqual(
            junctions.endpoint_id(left, 1),
            junctions.endpoint_id(right, 0),
        )
        self.assertTrue(junctions.endpoint_id(left, 1))
        self.assertEqual((left.positions, right.positions), before)
        self.assertEqual(
            (stats.clusters, stats.endpoints, stats.new_ids),
            (1, 2, 1),
        )

    def test_existing_id_survives_and_noncluster_endpoint_is_unchanged(self):
        left, right, remote = touching_pair_plus_remote()
        junctions.set_endpoint_id(left, 1, "keep-me")
        junctions.set_endpoint_id(right, 0, "drop-me")
        junctions.set_endpoint_id(remote, 0, "drop-me")

        stats = junctions.reconnect_touching_endpoints(
            [left, right, remote], 0.001
        )

        self.assertEqual(junctions.endpoint_id(left, 1), "keep-me")
        self.assertEqual(junctions.endpoint_id(right, 0), "keep-me")
        self.assertEqual(junctions.endpoint_id(remote, 0), "drop-me")
        self.assertEqual(stats.merged_ids, 1)

    def test_reconnect_clears_only_affected_hosted_attachment(self):
        left, right, remote = touching_pair_plus_remote()
        set_host_record(left, 1, "host-left")
        set_host_record(remote, 0, "host-remote")

        junctions.reconnect_touching_endpoints([left, right, remote], 0.001)

        self.assertIsNone(junctions.hosted_attachment(left, 1))
        self.assertEqual(
            junctions.hosted_attachment(remote, 0)["host_component_id"],
            "host-remote",
        )


if __name__ == "__main__":
    unittest.main()
