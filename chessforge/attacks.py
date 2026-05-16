"""Precomputed attack geometry for the chess board.

The engine currently uses a mailbox-style 64-square board.  Even with that
representation, fixed attack tables are worthwhile because king, knight, and
pawn geometry is independent of occupancy.  Centralizing those tables removes
duplicated boundary arithmetic from hot legality paths and creates a clean
bridge toward bitboard and magic-bitboard subsystems.
"""

from __future__ import annotations

from .constants import BLACK, KING_DELTAS, KNIGHT_DELTAS, WHITE, file_of, on_board, rank_of, square

AttackTable = tuple[tuple[int, ...], ...]


def _build_leaper_attacks(deltas: tuple[tuple[int, int], ...]) -> AttackTable:
    table: list[tuple[int, ...]] = []
    for source in range(64):
        file_index = file_of(source)
        rank_index = rank_of(source)
        targets: list[int] = []
        for df, dr in deltas:
            target_file = file_index + df
            target_rank = rank_index + dr
            if on_board(target_file, target_rank):
                targets.append(square(target_file, target_rank))
        table.append(tuple(targets))
    return tuple(table)


def _build_pawn_attacks(side: int) -> AttackTable:
    if side not in (WHITE, BLACK):
        raise ValueError(f"Invalid pawn attack side: {side}")
    direction = 1 if side == WHITE else -1
    table: list[tuple[int, ...]] = []
    for source in range(64):
        file_index = file_of(source)
        rank_index = rank_of(source)
        targets: list[int] = []
        for df in (-1, 1):
            target_file = file_index + df
            target_rank = rank_index + direction
            if on_board(target_file, target_rank):
                targets.append(square(target_file, target_rank))
        table.append(tuple(targets))
    return tuple(table)


def _invert_attack_table(table: AttackTable) -> AttackTable:
    """Return source squares that attack each target square.

    For symmetric leapers this is identical to the original table.  Pawns are
    directional, so attack detection needs the inverse mapping: given a target
    square, which pawn source squares of a color could attack it?
    """

    inverse: list[list[int]] = [[] for _ in range(64)]
    for source, targets in enumerate(table):
        for target in targets:
            inverse[target].append(source)
    return tuple(tuple(sources) for sources in inverse)


KNIGHT_ATTACKS = _build_leaper_attacks(KNIGHT_DELTAS)
KING_ATTACKS = _build_leaper_attacks(KING_DELTAS)

WHITE_PAWN_ATTACKS = _build_pawn_attacks(WHITE)
BLACK_PAWN_ATTACKS = _build_pawn_attacks(BLACK)

WHITE_PAWN_ATTACKERS = _invert_attack_table(WHITE_PAWN_ATTACKS)
BLACK_PAWN_ATTACKERS = _invert_attack_table(BLACK_PAWN_ATTACKS)
