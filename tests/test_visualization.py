import unittest

from chessforge.constants import WHITE
from chessforge.core import Position
from chessforge.visualization import attack_map, attack_map_text, evaluation_heatmap, principal_variation_report


class VisualizationTests(unittest.TestCase):
    def test_attack_map_and_text_are_deterministic(self) -> None:
        position = Position.starting()
        first = attack_map(position, WHITE)
        second = attack_map(position, WHITE)
        self.assertEqual(first, second)
        self.assertIn("a3", first)
        self.assertIn("*", attack_map_text(position, WHITE))

    def test_evaluation_heatmap_and_pv_report(self) -> None:
        position = Position.starting()
        heatmap = evaluation_heatmap(position)
        self.assertIn("e2e4", heatmap)
        report = principal_variation_report(position, 1)
        self.assertIn("best_move", report)
        self.assertIn("stats", report)


if __name__ == "__main__":
    unittest.main()

