import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def string_constants(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


class ReconnectUIContractTests(unittest.TestCase):
    def test_operator_id_exists_and_is_exposed_in_ui(self):
        operator_strings = string_constants(ROOT / "operators.py")
        ui_strings = string_constants(ROOT / "ui.py")
        self.assertIn("cpc.reconnect_touching_endpoints", operator_strings)
        self.assertIn("cpc.reconnect_touching_endpoints", ui_strings)

    def test_operator_class_is_registered(self):
        source = (ROOT / "operators.py").read_text(encoding="utf-8")
        self.assertIn("CPC_OT_ReconnectTouchingEndpoints", source.split("_CLASSES =", 1)[1])


if __name__ == "__main__":
    unittest.main()
