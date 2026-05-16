import unittest

from chessforge.core import Position
from chessforge.experiments import (
    EngineSpec,
    elo_from_score,
    parameter_sweep,
    play_game,
    round_robin,
    score_rate,
    sprt_log_likelihood,
)
from chessforge.search import SearchConfig


class ExperimentTests(unittest.TestCase):
    def test_play_game_and_round_robin_are_deterministic(self) -> None:
        spec_a = EngineSpec("a", SearchConfig(max_depth=1, time_limit=None))
        spec_b = EngineSpec("b", SearchConfig(max_depth=1, time_limit=None, use_pvs=False))
        fen = Position.starting().to_fen()
        self.assertEqual(play_game(spec_a, spec_b, fen, 4), play_game(spec_a, spec_b, fen, 4))
        records = round_robin([spec_a, spec_b], [fen], 2)
        self.assertEqual(len(records), 2)
        self.assertGreaterEqual(score_rate(records, "a"), 0.0)

    def test_elo_and_sprt_math_are_bounded(self) -> None:
        self.assertAlmostEqual(elo_from_score(0.5), 0.0)
        self.assertGreater(elo_from_score(0.75), 0.0)
        self.assertIsInstance(sprt_log_likelihood([1.0, 0.5, 0.0], 0.0, 5.0), float)

    def test_parameter_sweep_returns_rows(self) -> None:
        rows = parameter_sweep(Position.starting().to_fen(), [1], 2)
        self.assertTrue(rows)
        self.assertIn("score_rate", rows[0])


if __name__ == "__main__":
    unittest.main()

