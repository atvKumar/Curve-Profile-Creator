import unittest

from endpoint_reconnect import EndpointRecord, plan_reconnections


def endpoint(name, index, x, *, junction="", sequence=0):
    return EndpointRecord(name, index, (x, 0.0, 0.0), junction, sequence)


class EndpointReconnectPlanTests(unittest.TestCase):
    def test_boundary_is_inclusive_but_outside_point_is_unchanged(self):
        groups = plan_reconnections(
            [
                endpoint("a", 1, 0.0),
                endpoint("b", 0, 0.01),
                endpoint("c", 0, 0.020001),
            ],
            0.01,
        )
        self.assertEqual(
            [[member.object_key for member in group.members] for group in groups],
            [["a", "b"]],
        )

    def test_transitive_touching_points_form_one_cluster(self):
        groups = plan_reconnections(
            [
                endpoint("a", 1, 0.0),
                endpoint("b", 0, 0.009),
                endpoint("c", 0, 0.018),
            ],
            0.01,
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(
            {member.object_key for member in groups[0].members},
            {"a", "b", "c"},
        )

    def test_same_object_only_cluster_is_ignored(self):
        groups = plan_reconnections(
            [endpoint("a", 0, 0.0), endpoint("a", 1, 0.0)],
            0.01,
        )
        self.assertEqual(groups, ())

    def test_first_existing_id_in_stable_order_survives(self):
        groups = plan_reconnections(
            [
                endpoint(
                    "late", 0, 0.0, junction="junction-late", sequence=20
                ),
                endpoint(
                    "early", 1, 0.0, junction="junction-early", sequence=10
                ),
                endpoint("new", 0, 0.0, sequence=30),
            ],
            0.001,
        )
        self.assertEqual(groups[0].keep_id, "junction-early")
        self.assertEqual(groups[0].merged_ids, ("junction-late",))
        self.assertFalse(groups[0].needs_new_id)

    def test_cluster_without_id_requests_one_new_id(self):
        group = plan_reconnections(
            [endpoint("a", 1, 0.0), endpoint("b", 0, 0.0)],
            0.001,
        )[0]
        self.assertEqual(group.keep_id, "")
        self.assertTrue(group.needs_new_id)

    def test_invalid_tolerance_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_reconnections([endpoint("a", 0, 0.0)], 0.0)


if __name__ == "__main__":
    unittest.main()
