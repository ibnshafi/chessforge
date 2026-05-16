import random
import unittest

from chessforge.core import Position, compute_zobrist_hash
from chessforge.constants import opponent


class DeterministicFuzzTests(unittest.TestCase):
    def test_seeded_legal_playout_preserves_core_invariants(self) -> None:
        rng = random.Random(20260516)
        position = Position.starting()
        for _ply in range(24):
            self.assertEqual(position.to_fen(), Position.from_fen(position.to_fen()).to_fen())
            self.assertEqual(
                position.zobrist_hash,
                compute_zobrist_hash(position.board, position.turn, position.castling, position.ep_square),
            )
            moves = position.legal_moves()
            if not moves:
                break
            move = rng.choice(moves)
            child = position.make_move(move)
            self.assertFalse(child.is_in_check(opponent(child.turn)))
            self.assertEqual(child.king_square(1), child.white_king_square)
            self.assertEqual(child.king_square(-1), child.black_king_square)
            position = child


if __name__ == "__main__":
    unittest.main()

