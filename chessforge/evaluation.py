"""Static evaluation built from material, PST matrices, mobility, and king safety."""

from __future__ import annotations

from .constants import (
    BISHOP,
    BLACK,
    EMPTY,
    KING,
    KNIGHT,
    PAWN,
    PIECE_VALUES,
    QUEEN,
    ROOK,
    WHITE,
    color_of,
    file_of,
    on_board,
    opponent,
    piece_type,
    rank_of,
    square,
)
from .core import Position

# Piece-square matrices are stored from White's perspective with row 0 == rank 8.
# Black uses the same matrix mirrored vertically.
PAWN_PST = (
    (0, 0, 0, 0, 0, 0, 0, 0),
    (50, 50, 50, 50, 50, 50, 50, 50),
    (10, 10, 20, 30, 30, 20, 10, 10),
    (5, 5, 10, 25, 25, 10, 5, 5),
    (0, 0, 0, 20, 20, 0, 0, 0),
    (5, -5, -10, 0, 0, -10, -5, 5),
    (5, 10, 10, -20, -20, 10, 10, 5),
    (0, 0, 0, 0, 0, 0, 0, 0),
)

KNIGHT_PST = (
    (-50, -40, -30, -30, -30, -30, -40, -50),
    (-40, -20, 0, 5, 5, 0, -20, -40),
    (-30, 5, 10, 15, 15, 10, 5, -30),
    (-30, 0, 15, 20, 20, 15, 0, -30),
    (-30, 5, 15, 20, 20, 15, 5, -30),
    (-30, 0, 10, 15, 15, 10, 0, -30),
    (-40, -20, 0, 0, 0, 0, -20, -40),
    (-50, -40, -30, -30, -30, -30, -40, -50),
)

BISHOP_PST = (
    (-20, -10, -10, -10, -10, -10, -10, -20),
    (-10, 5, 0, 0, 0, 0, 5, -10),
    (-10, 10, 10, 10, 10, 10, 10, -10),
    (-10, 0, 10, 10, 10, 10, 0, -10),
    (-10, 5, 5, 10, 10, 5, 5, -10),
    (-10, 0, 5, 10, 10, 5, 0, -10),
    (-10, 0, 0, 0, 0, 0, 0, -10),
    (-20, -10, -10, -10, -10, -10, -10, -20),
)

ROOK_PST = (
    (0, 0, 0, 5, 5, 0, 0, 0),
    (5, 10, 10, 10, 10, 10, 10, 5),
    (-5, 0, 0, 0, 0, 0, 0, -5),
    (-5, 0, 0, 0, 0, 0, 0, -5),
    (-5, 0, 0, 0, 0, 0, 0, -5),
    (-5, 0, 0, 0, 0, 0, 0, -5),
    (-5, 0, 0, 0, 0, 0, 0, -5),
    (0, 0, 0, 5, 5, 0, 0, 0),
)

QUEEN_PST = (
    (-20, -10, -10, -5, -5, -10, -10, -20),
    (-10, 0, 0, 0, 0, 0, 0, -10),
    (-10, 0, 5, 5, 5, 5, 0, -10),
    (-5, 0, 5, 5, 5, 5, 0, -5),
    (0, 0, 5, 5, 5, 5, 0, -5),
    (-10, 5, 5, 5, 5, 5, 0, -10),
    (-10, 0, 5, 0, 0, 0, 0, -10),
    (-20, -10, -10, -5, -5, -10, -10, -20),
)

KING_MIDDLEGAME_PST = (
    (-30, -40, -40, -50, -50, -40, -40, -30),
    (-30, -40, -40, -50, -50, -40, -40, -30),
    (-30, -40, -40, -50, -50, -40, -40, -30),
    (-30, -40, -40, -50, -50, -40, -40, -30),
    (-20, -30, -30, -40, -40, -30, -30, -20),
    (-10, -20, -20, -20, -20, -20, -20, -10),
    (20, 20, 0, 0, 0, 0, 20, 20),
    (20, 30, 10, 0, 0, 10, 30, 20),
)

KING_ENDGAME_PST = (
    (-50, -30, -30, -30, -30, -30, -30, -50),
    (-30, -10, 0, 0, 0, 0, -10, -30),
    (-30, 0, 20, 30, 30, 20, 0, -30),
    (-30, 0, 30, 40, 40, 30, 0, -30),
    (-30, 0, 30, 40, 40, 30, 0, -30),
    (-30, 0, 20, 30, 30, 20, 0, -30),
    (-30, -10, 0, 0, 0, 0, -10, -30),
    (-50, -30, -30, -30, -30, -30, -30, -50),
)

PST = {
    PAWN: PAWN_PST,
    KNIGHT: KNIGHT_PST,
    BISHOP: BISHOP_PST,
    ROOK: ROOK_PST,
    QUEEN: QUEEN_PST,
    KING: KING_MIDDLEGAME_PST,
}


def _pst_lookup(piece: int, square_index: int, endgame_weight: float) -> int:
    kind = piece_type(piece)
    file_index = file_of(square_index)
    rank_index = rank_of(square_index)
    color = color_of(piece)
    row = 7 - rank_index if color == WHITE else rank_index
    if kind == KING:
        middle = KING_MIDDLEGAME_PST[row][file_index]
        end = KING_ENDGAME_PST[row][file_index]
        return round(middle * (1.0 - endgame_weight) + end * endgame_weight)
    return PST[kind][row][file_index]


def _endgame_weight(position: Position) -> float:
    non_pawn_material = 0
    starting_non_pawn = 2 * (2 * PIECE_VALUES[ROOK] + 2 * PIECE_VALUES[KNIGHT] + 2 * PIECE_VALUES[BISHOP] + PIECE_VALUES[QUEEN])
    for piece in position.board:
        if piece and piece_type(piece) not in (PAWN, KING):
            non_pawn_material += PIECE_VALUES[piece_type(piece)]
    return max(0.0, min(1.0, 1.0 - non_pawn_material / starting_non_pawn))


def _bishop_pair_score(position: Position) -> int:
    white_bishops = sum(1 for piece in position.board if piece == WHITE * BISHOP)
    black_bishops = sum(1 for piece in position.board if piece == BLACK * BISHOP)
    return (35 if white_bishops >= 2 else 0) - (35 if black_bishops >= 2 else 0)


def _mobility_score(position: Position) -> int:
    white = sum(1 for _move in position.generate_pseudo_legal_moves(WHITE))
    black = sum(1 for _move in position.generate_pseudo_legal_moves(BLACK))
    return 2 * (white - black)


def _pawn_squares(position: Position, color: int) -> list[int]:
    return [sq for sq, piece in enumerate(position.board) if piece == color * PAWN]


def _file_has_pawn(position: Position, color: int, file_index: int) -> bool:
    return any(file_of(sq) == file_index for sq in _pawn_squares(position, color))


def _is_passed_pawn(position: Position, sq: int, color: int) -> bool:
    pawn_file = file_of(sq)
    pawn_rank = rank_of(sq)
    enemy = opponent(color)
    for enemy_sq in _pawn_squares(position, enemy):
        enemy_file = file_of(enemy_sq)
        enemy_rank = rank_of(enemy_sq)
        if abs(enemy_file - pawn_file) > 1:
            continue
        if color == WHITE and enemy_rank > pawn_rank:
            return False
        if color == BLACK and enemy_rank < pawn_rank:
            return False
    return True


def _pawn_is_connected(position: Position, sq: int, color: int) -> bool:
    pawn_file = file_of(sq)
    pawn_rank = rank_of(sq)
    for friendly_sq in _pawn_squares(position, color):
        if friendly_sq == sq:
            continue
        if abs(file_of(friendly_sq) - pawn_file) == 1 and abs(rank_of(friendly_sq) - pawn_rank) <= 1:
            return True
    return False


def _pawn_is_backward(position: Position, sq: int, color: int) -> bool:
    pawn_file = file_of(sq)
    pawn_rank = rank_of(sq)
    support_rank = pawn_rank - 1 if color == WHITE else pawn_rank + 1
    for df in (-1, 1):
        support_file = pawn_file + df
        if on_board(support_file, support_rank) and position.board[square(support_file, support_rank)] == color * PAWN:
            return False
    advance_rank = pawn_rank + (1 if color == WHITE else -1)
    if not on_board(pawn_file, advance_rank):
        return False
    advance_sq = square(pawn_file, advance_rank)
    return position.is_square_attacked(advance_sq, opponent(color))


def _pawn_structure_for_color(position: Position, color: int) -> int:
    pawns = _pawn_squares(position, color)
    files = [0] * 8
    for sq in pawns:
        files[file_of(sq)] += 1
    score = 0
    for file_index, count in enumerate(files):
        if count > 1:
            score -= 14 * (count - 1)
        if count and not (
            (file_index > 0 and files[file_index - 1])
            or (file_index < 7 and files[file_index + 1])
        ):
            score -= 12 * count
    for sq in pawns:
        advancement = rank_of(sq) if color == WHITE else 7 - rank_of(sq)
        if _is_passed_pawn(position, sq, color):
            score += 10 + advancement * advancement * 2
            if _pawn_is_connected(position, sq, color):
                score += 12 + advancement
        elif _pawn_is_backward(position, sq, color):
            score -= 8
    return score


def _pawn_structure_score(position: Position) -> int:
    return _pawn_structure_for_color(position, WHITE) - _pawn_structure_for_color(position, BLACK)


def _rook_file_score_for_color(position: Position, color: int) -> int:
    score = 0
    for sq, piece in enumerate(position.board):
        if piece != color * ROOK:
            continue
        file_index = file_of(sq)
        friendly_pawn = _file_has_pawn(position, color, file_index)
        enemy_pawn = _file_has_pawn(position, opponent(color), file_index)
        if not friendly_pawn and not enemy_pawn:
            score += 22
        elif not friendly_pawn and enemy_pawn:
            score += 12
        rank_index = rank_of(sq)
        if (color == WHITE and rank_index == 6) or (color == BLACK and rank_index == 1):
            score += 18
    return score


def _rook_file_score(position: Position) -> int:
    return _rook_file_score_for_color(position, WHITE) - _rook_file_score_for_color(position, BLACK)


def _is_pawn_protected(position: Position, sq: int, color: int) -> bool:
    rank_delta = -1 if color == WHITE else 1
    for df in (-1, 1):
        file_index = file_of(sq) + df
        rank_index = rank_of(sq) + rank_delta
        if on_board(file_index, rank_index) and position.board[square(file_index, rank_index)] == color * PAWN:
            return True
    return False


def _enemy_pawn_can_challenge(position: Position, sq: int, color: int) -> bool:
    enemy = opponent(color)
    target_file = file_of(sq)
    target_rank = rank_of(sq)
    for enemy_sq in _pawn_squares(position, enemy):
        if abs(file_of(enemy_sq) - target_file) != 1:
            continue
        if color == WHITE and rank_of(enemy_sq) > target_rank:
            return True
        if color == BLACK and rank_of(enemy_sq) < target_rank:
            return True
    return False


def _outpost_score_for_color(position: Position, color: int) -> int:
    score = 0
    for sq, piece in enumerate(position.board):
        if piece not in (color * KNIGHT, color * BISHOP):
            continue
        rank_index = rank_of(sq)
        in_enemy_half = rank_index >= 3 if color == WHITE else rank_index <= 4
        if in_enemy_half and _is_pawn_protected(position, sq, color) and not _enemy_pawn_can_challenge(position, sq, color):
            score += 24 if piece_type(piece) == KNIGHT else 12
    return score


def _outpost_score(position: Position) -> int:
    return _outpost_score_for_color(position, WHITE) - _outpost_score_for_color(position, BLACK)


def _king_tropism_for_color(position: Position, color: int) -> int:
    enemy_king = position.king_square(opponent(color))
    enemy_file = file_of(enemy_king)
    enemy_rank = rank_of(enemy_king)
    score = 0
    weights = {KNIGHT: 3, BISHOP: 2, ROOK: 2, QUEEN: 5}
    for sq, piece in enumerate(position.board):
        if piece == EMPTY or color_of(piece) != color:
            continue
        kind = piece_type(piece)
        if kind not in weights:
            continue
        distance = abs(file_of(sq) - enemy_file) + abs(rank_of(sq) - enemy_rank)
        score += max(0, 14 - distance) * weights[kind]
    return score


def _king_tropism_score(position: Position) -> int:
    return _king_tropism_for_color(position, WHITE) - _king_tropism_for_color(position, BLACK)


def _space_for_color(position: Position, color: int) -> int:
    score = 0
    ranks = range(2, 5) if color == WHITE else range(3, 6)
    for rank_index in ranks:
        for file_index in range(2, 6):
            sq = square(file_index, rank_index)
            if position.board[sq] == EMPTY and not position.is_square_attacked(sq, opponent(color)):
                score += 2
    return score


def _space_score(position: Position) -> int:
    return _space_for_color(position, WHITE) - _space_for_color(position, BLACK)


def _threat_score_for_color(position: Position, color: int) -> int:
    score = 0
    enemy = opponent(color)
    for sq, piece in enumerate(position.board):
        if piece == EMPTY or color_of(piece) != enemy or piece_type(piece) == KING:
            continue
        if position.is_square_attacked(sq, color):
            score += max(4, PIECE_VALUES[piece_type(piece)] // 20)
    return score


def _threat_score(position: Position) -> int:
    return _threat_score_for_color(position, WHITE) - _threat_score_for_color(position, BLACK)


def _tempo_score(position: Position) -> int:
    return 12 if position.turn == WHITE else -12


def _king_opposition_score(position: Position, endgame_weight: float) -> int:
    if endgame_weight < 0.75:
        return 0
    white_king = position.king_square(WHITE)
    black_king = position.king_square(BLACK)
    distance = abs(file_of(white_king) - file_of(black_king)) + abs(rank_of(white_king) - rank_of(black_king))
    if distance != 2:
        return 0
    side_bonus = -10 if position.turn == WHITE else 10
    return round(side_bonus * endgame_weight)


def _fortress_scaling(position: Position, score: int, endgame_weight: float) -> int:
    if endgame_weight < 0.85:
        return score
    non_king_pieces = [piece for piece in position.board if piece and piece_type(piece) != KING]
    if len(non_king_pieces) <= 2 and abs(score) < 350:
        return round(score * 0.65)
    return score


def _pawn_shield(position: Position, color: int) -> int:
    king_sq = position.king_square(color)
    king_file = file_of(king_sq)
    king_rank = rank_of(king_sq)
    direction = 1 if color == WHITE else -1
    shield = 0
    for df in (-1, 0, 1):
        file_index = king_file + df
        rank_index = king_rank + direction
        if on_board(file_index, rank_index) and position.board[square(file_index, rank_index)] == color * PAWN:
            shield += 10
        rank_index = king_rank + 2 * direction
        if on_board(file_index, rank_index) and position.board[square(file_index, rank_index)] == color * PAWN:
            shield += 4
    return shield


def _king_attack_pressure(position: Position, color: int) -> int:
    king_sq = position.king_square(color)
    king_file = file_of(king_sq)
    king_rank = rank_of(king_sq)
    attackers = 0
    for df in (-1, 0, 1):
        for dr in (-1, 0, 1):
            if df == 0 and dr == 0:
                continue
            file_index = king_file + df
            rank_index = king_rank + dr
            if on_board(file_index, rank_index) and position.is_square_attacked(square(file_index, rank_index), opponent(color)):
                attackers += 1
    return attackers * 6


def evaluate(position: Position) -> int:
    """Return a centipawn score: positive favors White, negative favors Black."""

    score = position.material_balance
    endgame = _endgame_weight(position)
    for sq, piece in enumerate(position.board):
        if piece == EMPTY:
            continue
        sign = 1 if color_of(piece) == WHITE else -1
        score += sign * _pst_lookup(piece, sq, endgame)

    score += _bishop_pair_score(position)
    score += _mobility_score(position)
    score += _pawn_structure_score(position)
    score += _rook_file_score(position)
    score += _outpost_score(position)
    score += _king_tropism_score(position)
    score += _space_score(position)
    score += _threat_score(position)
    score += _pawn_shield(position, WHITE) - _pawn_shield(position, BLACK)
    score -= _king_attack_pressure(position, WHITE)
    score += _king_attack_pressure(position, BLACK)
    score += _tempo_score(position)
    score += _king_opposition_score(position, endgame)
    return _fortress_scaling(position, score, endgame)
