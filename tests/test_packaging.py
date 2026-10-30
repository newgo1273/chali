import unittest
from pathlib import Path


class DebianMetadataTests(unittest.TestCase):
    def test_control_declares_architecture_independent_runtime(self):
        control = (Path(__file__).parents[1] / "packaging" / "DEBIAN" / "control").read_text(
            encoding="utf-8"
        )
        self.assertIn("Package: chali\n", control)
        self.assertIn("Architecture: all\n", control)
        self.assertIn("python3 (>= 3.9)", control)
        self.assertIn("python3-pip", control)
        self.assertIn("python3-textual", control)


if __name__ == "__main__":
    unittest.main()
