import unittest

from chessforge.bitboards import BitboardView, attack_mask, bit, iter_bits, popcount
from chessforge.constants import BLACK, KNIGHT, QUEEN, WHITE, parse_square
from chessforge.core import Position


class BitboardViewTests(unittest.TestCase):
    def test_starting_position_occupancy_masks(self) -> None:
        view = BitboardView.from_position(Position.starting())
        self.assertEqual(popcount(view.white), 16)
        self.assertEqual(popcount(view.black), 16)
        self.assertEqual(popcount(view.occupied), 32)
        self.assertEqual(view.white & view.black, 0)

    def test_piece_mask_tracks_signed_piece_encoding(self) -> None:
        view = BitboardView.from_position(Position.starting())
        self.assertEqual(set(iter_bits(view.piece_mask(WHITE * KNIGHT))), {parse_square("b1"), parse_square("g1")})
        self.assertEqual(set(iter_bits(view.piece_mask(BLACK * QUEEN))), {parse_square("d8")})

    def test_attack_mask_matches_expected_knight_geometry(self) -> None:
        source = parse_square("d4")
        attacks = attack_mask(WHITE * KNIGHT, source, 0)
        self.assertEqual(
            set(iter_bits(attacks)),
            {
                parse_square("b3"),
                parse_square("b5"),
                parse_square("c2"),
                parse_square("c6"),
                parse_square("e2"),
                parse_square("e6"),
                parse_square("f3"),
                parse_square("f5"),
            },
        )

    def test_sliding_attack_mask_stops_at_first_blocker(self) -> None:
        source = parse_square("d4")
        occupancy = bit(parse_square("d6")) | bit(parse_square("f4"))
        attacks = attack_mask(WHITE * QUEEN, source, occupancy)
        self.assertIn(parse_square("d6"), set(iter_bits(attacks)))
        self.assertNotIn(parse_square("d7"), set(iter_bits(attacks)))
        self.assertIn(parse_square("f4"), set(iter_bits(attacks)))
        self.assertNotIn(parse_square("g4"), set(iter_bits(attacks)))


if __name__ == "__main__":
    unittest.main()

