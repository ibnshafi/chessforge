"""Hybrid bitboard views over the canonical mailbox ``Position``.

ChessForge keeps ``Position.board`` as the authoritative representation today.
This module builds deterministic bitboard views from that mailbox state.  The
view is intentionally immutable and derived: it cannot corrupt legal move
generation, yet it exposes the memory layout and attack-mask vocabulary needed
for magic bitboards, pinned masks, visualization, NNUE features, and profiling.
"""

from __future__ import annotations

from dataclasses import dataclass

from .attacks import BLACK_PAWN_ATTACKS, KING_ATTACKS, KNIGHT_ATTACKS, WHITE_PAWN_ATTACKS
from .constants import (
    BISHOP,
    BISHOP_DIRECTIONS,
    BLACK,
    EMPTY,
    KING,
    KNIGHT,
    PAWN,
    QUEEN,
    ROOK,
    ROOK_DIRECTIONS,
    WHITE,
    color_of,
    file_of,
    on_board,
    piece_type,
    rank_of,
    square,
)
from .core import Position

FULL_BOARD = (1 << 64) - 1


def bit(square_index: int) -> int:
    return 1 << square_index


def iter_bits(mask: int):
    while mask:
        lsb = mask & -mask
        yield lsb.bit_length() - 1
        mask ^= lsb


def popcount(mask: int) -> int:
    return mask.bit_count()


def _ray_mask(source: int, directions: tuple[tuple[int, int], ...], occupancy: int) -> int:
    attacks = 0
    source_file = file_of(source)
    source_rank = rank_of(source)
    for df, dr in directions:
        target_file = source_file + df
        target_rank = source_rank + dr
        while on_board(target_file, target_rank):
            target = square(target_file, target_rank)
            target_bit = bit(target)
            attacks |= target_bit
            if occupancy & target_bit:
                break
            target_file += df
            target_rank += dr
    return attacks


def attack_mask(piece: int, source: int, occupancy: int) -> int:
    kind = piece_type(piece)
    color = color_of(piece)
    if kind == PAWN:
        table = WHITE_PAWN_ATTACKS if color == WHITE else BLACK_PAWN_ATTACKS
        return sum(bit(target) for target in table[source])
    if kind == KNIGHT:
        return sum(bit(target) for target in KNIGHT_ATTACKS[source])
    if kind == KING:
        return sum(bit(target) for target in KING_ATTACKS[source])
    if kind == BISHOP:
        return _ray_mask(source, BISHOP_DIRECTIONS, occupancy)
    if kind == ROOK:
        return _ray_mask(source, ROOK_DIRECTIONS, occupancy)
    if kind == QUEEN:
        return _ray_mask(source, BISHOP_DIRECTIONS + ROOK_DIRECTIONS, occupancy)
    return 0


@dataclass(frozen=True, slots=True)
class BitboardView:
    white: int
    black: int
    occupied: int
    empty: int
    pieces: tuple[int, ...]

    @classmethod
    def from_position(cls, position: Position) -> "BitboardView":
        pieces = [0] * 13
        white = 0
        black = 0
        for sq, piece in enumerate(position.board):
            if piece == EMPTY:
                continue
            sq_bit = bit(sq)
            pieces[_piece_index(piece)] |= sq_bit
            if piece > 0:
                white |= sq_bit
            else:
                black |= sq_bit
        occupied = white | black
        return cls(white=white, black=black, occupied=occupied, empty=FULL_BOARD ^ occupied, pieces=tuple(pieces))

    def piece_mask(self, piece: int) -> int:
        return self.pieces[_piece_index(piece)]

    def color_mask(self, color: int) -> int:
        if color == WHITE:
            return self.white
        if color == BLACK:
            return self.black
        return 0

    def attacks_for_piece(self, piece: int, source: int) -> int:
        return attack_mask(piece, source, self.occupied)

    def all_attacks(self, position: Position, color: int) -> int:
        attacks = 0
        color_mask = self.color_mask(color)
        for source in iter_bits(color_mask):
            piece = position.board[source]
            attacks |= self.attacks_for_piece(piece, source)
        return attacks


def _piece_index(piece: int) -> int:
    kind = piece_type(piece)
    return kind if piece > 0 else kind + 6

