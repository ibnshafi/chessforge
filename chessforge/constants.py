"""Core constants and square helpers.

The board uses 0..63 indexing with a1 == 0 and h8 == 63. Positive pieces
are white, negative pieces are black, and piece magnitude stores the type.
"""

from __future__ import annotations

WHITE = 1
BLACK = -1
EMPTY = 0

PAWN = 1
KNIGHT = 2
BISHOP = 3
ROOK = 4
QUEEN = 5
KING = 6

PIECE_VALUES = {
    PAWN: 100,
    KNIGHT: 320,
    BISHOP: 330,
    ROOK: 500,
    QUEEN: 900,
    KING: 0,
}

FILES = "abcdefgh"
RANKS = "12345678"

WK_CASTLE = 1
WQ_CASTLE = 2
BK_CASTLE = 4
BQ_CASTLE = 8
ALL_CASTLING = WK_CASTLE | WQ_CASTLE | BK_CASTLE | BQ_CASTLE

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

PIECE_TO_CHAR = {
    WHITE * PAWN: "P",
    WHITE * KNIGHT: "N",
    WHITE * BISHOP: "B",
    WHITE * ROOK: "R",
    WHITE * QUEEN: "Q",
    WHITE * KING: "K",
    BLACK * PAWN: "p",
    BLACK * KNIGHT: "n",
    BLACK * BISHOP: "b",
    BLACK * ROOK: "r",
    BLACK * QUEEN: "q",
    BLACK * KING: "k",
    EMPTY: ".",
}

CHAR_TO_PIECE = {v: k for k, v in PIECE_TO_CHAR.items() if v != "."}

PROMOTION_CHARS = {
    "n": KNIGHT,
    "b": BISHOP,
    "r": ROOK,
    "q": QUEEN,
}

PROMOTION_PIECES = (KNIGHT, BISHOP, ROOK, QUEEN)

KNIGHT_DELTAS = (
    (-2, -1),
    (-2, 1),
    (-1, -2),
    (-1, 2),
    (1, -2),
    (1, 2),
    (2, -1),
    (2, 1),
)

KING_DELTAS = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)

BISHOP_DIRECTIONS = ((1, 1), (1, -1), (-1, 1), (-1, -1))
ROOK_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))
QUEEN_DIRECTIONS = BISHOP_DIRECTIONS + ROOK_DIRECTIONS


def opponent(color: int) -> int:
    return -color


def color_of(piece: int) -> int:
    if piece > 0:
        return WHITE
    if piece < 0:
        return BLACK
    return EMPTY


def piece_type(piece: int) -> int:
    return abs(piece)


def square(file_index: int, rank_index: int) -> int:
    return rank_index * 8 + file_index


def file_of(square_index: int) -> int:
    return square_index & 7


def rank_of(square_index: int) -> int:
    return square_index >> 3


def on_board(file_index: int, rank_index: int) -> bool:
    return 0 <= file_index < 8 and 0 <= rank_index < 8


def square_name(square_index: int) -> str:
    if not 0 <= square_index < 64:
        raise ValueError(f"Square index out of range: {square_index}")
    return FILES[file_of(square_index)] + RANKS[rank_of(square_index)]


def parse_square(name: str) -> int:
    if len(name) != 2 or name[0] not in FILES or name[1] not in RANKS:
        raise ValueError(f"Invalid square: {name!r}")
    return square(FILES.index(name[0]), RANKS.index(name[1]))


def castling_to_text(castling: int) -> str:
    text = ""
    if castling & WK_CASTLE:
        text += "K"
    if castling & WQ_CASTLE:
        text += "Q"
    if castling & BK_CASTLE:
        text += "k"
    if castling & BQ_CASTLE:
        text += "q"
    return text or "-"


def text_to_castling(text: str) -> int:
    if text == "-":
        return 0
    rights = 0
    seen: set[str] = set()
    for char in text:
        if char in seen:
            raise ValueError(f"Duplicate castling flag in FEN: {text!r}")
        seen.add(char)
        if char == "K":
            rights |= WK_CASTLE
        elif char == "Q":
            rights |= WQ_CASTLE
        elif char == "k":
            rights |= BK_CASTLE
        elif char == "q":
            rights |= BQ_CASTLE
        else:
            raise ValueError(f"Invalid castling flag in FEN: {char!r}")
    return rights
