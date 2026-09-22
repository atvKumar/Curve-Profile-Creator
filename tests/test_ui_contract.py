import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UIContractTests(unittest.TestCase):
    def test_selected_part_panel_exposes_semantic_rotate_and_size_operators(self):
        source = (ROOT / "ui.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        operator_ids = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "operator"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }
        self.assertIn("cpc.component_rotate", operator_ids)
        self.assertIn("cpc.component_resize", operator_ids)

    def test_extension_register_does_not_eagerly_install_overlay_handlers(self):
        source = (ROOT / "__init__.py").read_text(encoding="utf-8")
        register_body = source.split("def register():", 1)[1].split(
            "def unregister():", 1
        )[0]
        self.assertNotIn("ensure_handlers", register_body)


if __name__ == "__main__":
    unittest.main()
