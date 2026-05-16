import unittest

from chessforge.core import Position, perft


class PerftTests(unittest.TestCase):
    def assert_perft(self, fen: str, expected: dict[int, int]) -> None:
        position = Position.from_fen(fen)
        for depth, nodes in expected.items():
            with self.subTest(depth=depth):
                self.assertEqual(perft(position, depth), nodes)

    def test_starting_position(self) -> None:
        self.assert_perft(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            {1: 20, 2: 400, 3: 8902},
        )

    def test_kiwipete_castling_and_pins(self) -> None:
        self.assert_perft(
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
            {1: 48, 2: 2039, 3: 97862},
        )

    def test_en_passant_and_complex_endgame(self) -> None:
        self.assert_perft(
            "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
            {1: 14, 2: 191, 3: 2812},
        )


if __name__ == "__main__":
    unittest.main()
