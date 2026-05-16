import tempfile
import unittest
from pathlib import Path

from chessforge.research import main


class ResearchCliTests(unittest.TestCase):
    def test_research_cli_writes_exports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "research.json"
            csv_path = Path(temp_dir) / "research.csv"
            code = main([
                "--depths",
                "1",
                "--max-plies",
                "2",
                "--json",
                str(json_path),
                "--csv",
                str(csv_path),
            ])
            self.assertEqual(code, 0)
            self.assertTrue(json_path.exists())
            self.assertTrue(csv_path.exists())


if __name__ == "__main__":
    unittest.main()

