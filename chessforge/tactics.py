"""Tactical helpers used by search and move ordering."""

from __future__ import annotations

from .constants import KING, PAWN, PIECE_VALUES, color_of, opponent, piece_type
from .core import Move, Position, _is_square_attacked_on_board


def capture_value(position: Position, move: Move) -> int:
    """Return the material value captured by ``move`` in centipawns."""

    attacker = position.board[move.from_sq]
    if move.is_en_passant:
        return PIECE_VALUES[PAWN]
    victim = position.board[move.to_sq]
    return PIECE_VALUES[piece_type(victim)] if victim else 0


def static_exchange_evaluation(position: Position, move: Move) -> int:
    """Conservative one-ply static exchange estimate.

    Full SEE recursively alternates the least valuable attackers after a
    capture and is best implemented over attack bitboards.  This mailbox
    version intentionally uses a safe approximation for ordering and pruning:
    captured value minus moving piece value when the destination is defended.
    It never rejects a legal move by itself; search uses it as a heuristic.
    """

    attacker = position.board[move.from_sq]
    if not attacker:
        return 0
    gain = capture_value(position, move)
    if move.promotion:
        gain += PIECE_VALUES[move.promotion] - PIECE_VALUES[PAWN]
    if not gain:
        return 0
    side = color_of(attacker)
    moving_value = PIECE_VALUES[piece_type(attacker)]
    board, moving_piece, _captured_piece, _captured_square = position._apply_move_to_board(move)
    defended = _is_square_attacked_on_board(board, move.to_sq, opponent(side))
    if defended and piece_type(moving_piece) != KING:
        gain -= moving_value
    return gain
