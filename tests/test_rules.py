import unittest

from chessforge.constants import BLACK, PAWN, QUEEN, ROOK, WHITE, parse_square
from chessforge.core import Position


class RuleTests(unittest.TestCase):
    def test_fen_round_trip(self) -> None:
        fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        self.assertEqual(Position.from_fen(fen).to_fen(), fen)

    def test_castling_moves_rook_and_clears_rights(self) -> None:
        position = Position.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        self.assertIn("e1g1", {move.uci() for move in position.legal_moves()})
        child = position.make_move(position.parse_uci_move("e1g1"))
        self.assertEqual(child.piece_at(parse_square("g1")), WHITE * 6)
        self.assertEqual(child.king_square(WHITE), parse_square("g1"))
        self.assertEqual(child.piece_at(parse_square("f1")), WHITE * ROOK)
        self.assertEqual(child.castling & 0b0011, 0)

    def test_castling_through_attacked_square_is_illegal(self) -> None:
        position = Position.from_fen("r3k2r/8/8/8/2b5/8/8/R3K2R w KQkq - 0 1")
        moves = {move.uci() for move in position.legal_moves()}
        self.assertNotIn("e1g1", moves)
        self.assertIn("e1c1", moves)

    def test_en_passant_capture_updates_board(self) -> None:
        position = Position.from_fen("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3")
        move = position.parse_uci_move("e5d6")
        self.assertTrue(move.is_en_passant)
        child = position.make_move(move)
        self.assertEqual(child.piece_at(parse_square("d6")), WHITE * PAWN)
        self.assertEqual(child.piece_at(parse_square("d5")), 0)

    def test_en_passant_cannot_expose_own_king(self) -> None:
        position = Position.from_fen("8/8/8/8/R1pP2k1/8/8/K7 b - d3 0 1")
        self.assertNotIn("c4d3", {move.uci() for move in position.legal_moves()})

    def test_promotion_choices(self) -> None:
        position = Position.from_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
        self.assertEqual(
            {"a7a8n", "a7a8b", "a7a8r", "a7a8q"},
            {move.uci() for move in position.legal_moves() if move.uci().startswith("a7a8")},
        )
        child = position.make_move(position.parse_uci_move("a7a8q"))
        self.assertEqual(child.piece_at(parse_square("a8")), WHITE * QUEEN)
        self.assertEqual(child.material_balance, 900)

    def test_incremental_material_updates_after_black_promotion(self) -> None:
        position = Position.from_fen("4k3/8/8/8/8/8/4p3/K7 b - - 0 1")
        child = position.make_move(position.parse_uci_move("e2e1q"))
        self.assertEqual(child.material_balance, -900)

    def test_checkmate_and_stalemate_detection(self) -> None:
        mate = Position.from_fen("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        self.assertEqual(mate.status().state, "checkmate")
        self.assertEqual(mate.status().winner, WHITE)

        stalemate = Position.from_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertEqual(stalemate.status().state, "stalemate")

    def test_threefold_repetition_detection(self) -> None:
        position = Position.starting()
        for uci in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
            position = position.make_move(position.parse_uci_move(uci))
        self.assertTrue(position.is_threefold_repetition())
        self.assertEqual(position.status().state, "draw")

    def test_fifty_move_rule_detection(self) -> None:
        position = Position.from_fen("8/8/8/8/8/8/6k1/4K3 w - - 100 1")
        self.assertTrue(position.is_fifty_move_rule())
        self.assertEqual(position.status().reason, "50-move rule")


if __name__ == "__main__":
    unittest.main()
