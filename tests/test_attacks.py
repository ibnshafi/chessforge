import unittest

from chessforge.attacks import (
    BLACK_PAWN_ATTACKERS,
    BLACK_PAWN_ATTACKS,
    KING_ATTACKS,
    KNIGHT_ATTACKS,
    WHITE_PAWN_ATTACKERS,
    WHITE_PAWN_ATTACKS,
)
from chessforge.constants import BLACK, WHITE, parse_square, square_name
from chessforge.core import Position


def names(squares: tuple[int, ...]) -> set[str]:
    return {square_name(square) for square in squares}


class AttackTableTests(unittest.TestCase):
    def test_knight_attack_geometry(self) -> None:
        self.assertEqual(
            {"b3", "b5", "c2", "c6", "e2", "e6", "f3", "f5"},
            names(KNIGHT_ATTACKS[parse_square("d4")]),
        )
        self.assertEqual({"b3", "c2"}, names(KNIGHT_ATTACKS[parse_square("a1")]))

    def test_king_attack_geometry(self) -> None:
        self.assertEqual({"a2", "b1", "b2"}, names(KING_ATTACKS[parse_square("a1")]))
        self.assertEqual(
            {"c3", "c4", "c5", "d3", "d5", "e3", "e4", "e5"},
            names(KING_ATTACKS[parse_square("d4")]),
        )

    def test_pawn_attack_direction_and_inverse_tables(self) -> None:
        self.assertEqual({"d5", "f5"}, names(WHITE_PAWN_ATTACKS[parse_square("e4")]))
        self.assertEqual({"d3", "f3"}, names(BLACK_PAWN_ATTACKS[parse_square("e4")]))
        self.assertEqual({"d3", "f3"}, names(WHITE_PAWN_ATTACKERS[parse_square("e4")]))
        self.assertEqual({"d5", "f5"}, names(BLACK_PAWN_ATTACKERS[parse_square("e4")]))

    def test_position_attack_detection_uses_precomputed_geometry(self) -> None:
        knight_check = Position.from_fen("4k3/8/8/8/4n3/8/3K4/8 w - - 0 1")
        self.assertTrue(knight_check.is_square_attacked(parse_square("d2"), BLACK))
        self.assertFalse(knight_check.is_square_attacked(parse_square("d2"), WHITE))

        pawn_pressure = Position.from_fen("4k3/8/8/3p1p2/4K3/8/8/8 w - - 0 1")
        self.assertTrue(pawn_pressure.is_square_attacked(parse_square("e4"), BLACK))


if __name__ == "__main__":
    unittest.main()
