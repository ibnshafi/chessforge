import unittest

from chessforge.core import Position
from chessforge.evaluation import evaluate


class EvaluationTests(unittest.TestCase):
    def test_passed_pawn_scores_above_blocked_pawn(self) -> None:
        passed = Position.from_fen("4k3/8/8/4P3/8/8/8/4K3 w - - 0 1")
        blocked = Position.from_fen("4k3/8/4p3/4P3/8/8/8/4K3 w - - 0 1")
        self.assertGreater(evaluate(passed), evaluate(blocked))

    def test_rook_on_open_file_is_rewarded(self) -> None:
        open_file = Position.from_fen("4k3/8/8/8/8/8/1P6/R3K3 w - - 0 1")
        blocked_file = Position.from_fen("4k3/8/8/8/8/8/P7/R3K3 w - - 0 1")
        self.assertGreater(evaluate(open_file), evaluate(blocked_file))

    def test_tempo_changes_with_side_to_move(self) -> None:
        white = Position.from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        black = Position.from_fen("4k3/8/8/8/8/8/8/4K3 b - - 0 1")
        self.assertGreater(evaluate(white), evaluate(black))


if __name__ == "__main__":
    unittest.main()
