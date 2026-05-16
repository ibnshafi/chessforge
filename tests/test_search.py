import unittest

from chessforge.core import Position
from chessforge.search import SearchConfig, SearchEngine


class SearchTests(unittest.TestCase):
    def test_search_returns_legal_move(self) -> None:
        position = Position.starting()
        result = SearchEngine().search(position, SearchConfig(max_depth=2, time_limit=2.0))
        self.assertIsNotNone(result.best_move)
        self.assertIn(result.best_move.uci(), {move.uci() for move in position.legal_moves()})

    def test_search_handles_terminal_position(self) -> None:
        position = Position.from_fen("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        result = SearchEngine().search(position, SearchConfig(max_depth=2, time_limit=1.0))
        self.assertIsNone(result.best_move)


if __name__ == "__main__":
    unittest.main()
