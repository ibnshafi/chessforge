"""Rules engine, legal move generation, FEN, game state, and perft."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

from .attacks import BLACK_PAWN_ATTACKERS, KING_ATTACKS, KNIGHT_ATTACKS, WHITE_PAWN_ATTACKERS
from .constants import (
    ALL_CASTLING,
    BISHOP,
    BISHOP_DIRECTIONS,
    BK_CASTLE,
    BLACK,
    BQ_CASTLE,
    CHAR_TO_PIECE,
    EMPTY,
    KING,
    KNIGHT,
    PAWN,
    PIECE_TO_CHAR,
    PIECE_VALUES,
    PROMOTION_CHARS,
    PROMOTION_PIECES,
    QUEEN,
    QUEEN_DIRECTIONS,
    ROOK,
    ROOK_DIRECTIONS,
    STARTING_FEN,
    WHITE,
    WK_CASTLE,
    WQ_CASTLE,
    castling_to_text,
    color_of,
    file_of,
    on_board,
    opponent,
    parse_square,
    piece_type,
    rank_of,
    square,
    square_name,
    text_to_castling,
)
from .move import Move

NO_SQUARE = -1
MAX_HASH = 0xFFFFFFFFFFFFFFFF
A1 = parse_square("a1")
B1 = parse_square("b1")
C1 = parse_square("c1")
D1 = parse_square("d1")
E1 = parse_square("e1")
F1 = parse_square("f1")
G1 = parse_square("g1")
H1 = parse_square("h1")
A8 = parse_square("a8")
B8 = parse_square("b8")
C8 = parse_square("c8")
D8 = parse_square("d8")
E8 = parse_square("e8")
F8 = parse_square("f8")
G8 = parse_square("g8")
H8 = parse_square("h8")


class ChessError(ValueError):
    """Raised when invalid chess input or state is detected."""


@dataclass(frozen=True, slots=True)
class GameStatus:
    """Structured game status for callers and interfaces."""

    state: str
    winner: int | None = None
    reason: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.state in {"checkmate", "stalemate", "draw"}


def _splitmix64(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & MAX_HASH
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MAX_HASH
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MAX_HASH
    return (value ^ (value >> 31)) & MAX_HASH


def _build_zobrist() -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...], tuple[int, ...], int]:
    seed = 0xC0DEFACE12345678
    piece_keys: list[tuple[int, ...]] = []
    current = seed
    for _ in range(12):
        row: list[int] = []
        for _square in range(64):
            current = _splitmix64(current)
            row.append(current)
        piece_keys.append(tuple(row))
    castling_keys: list[int] = []
    for _ in range(16):
        current = _splitmix64(current)
        castling_keys.append(current)
    ep_keys: list[int] = []
    for _ in range(8):
        current = _splitmix64(current)
        ep_keys.append(current)
    current = _splitmix64(current)
    turn_key = current
    return tuple(piece_keys), tuple(castling_keys), tuple(ep_keys), turn_key


ZOBRIST_PIECES, ZOBRIST_CASTLING, ZOBRIST_EP_FILE, ZOBRIST_BLACK_TO_MOVE = _build_zobrist()


def _zobrist_piece_index(piece: int) -> int:
    base = 0 if piece > 0 else 6
    return base + piece_type(piece) - 1


def _effective_ep_square(board: tuple[int, ...], turn: int, ep_square: int) -> int:
    """Return the en-passant square only when a pawn can plausibly use it.

    FEN strings may contain an en-passant target even when no capture is
    actually available. Repetition keys should represent available moves, so
    impossible targets are omitted from the hash.
    """

    if ep_square == NO_SQUARE:
        return NO_SQUARE
    ep_rank = rank_of(ep_square)
    ep_file = file_of(ep_square)
    if turn == WHITE:
        if ep_rank != 5:
            return NO_SQUARE
        candidates = ((ep_file - 1, 4), (ep_file + 1, 4))
        pawn = WHITE * PAWN
    else:
        if ep_rank != 2:
            return NO_SQUARE
        candidates = ((ep_file - 1, 3), (ep_file + 1, 3))
        pawn = BLACK * PAWN
    for file_index, rank_index in candidates:
        if on_board(file_index, rank_index) and board[square(file_index, rank_index)] == pawn:
            return ep_square
    return NO_SQUARE


def compute_zobrist_hash(
    board: tuple[int, ...],
    turn: int,
    castling: int,
    ep_square: int,
) -> int:
    value = 0
    for sq, piece in enumerate(board):
        if piece:
            value ^= ZOBRIST_PIECES[_zobrist_piece_index(piece)][sq]
    value ^= ZOBRIST_CASTLING[castling & ALL_CASTLING]
    effective_ep = _effective_ep_square(board, turn, ep_square)
    if effective_ep != NO_SQUARE:
        value ^= ZOBRIST_EP_FILE[file_of(effective_ep)]
    if turn == BLACK:
        value ^= ZOBRIST_BLACK_TO_MOVE
    return value & MAX_HASH


def _material_balance(board: tuple[int, ...]) -> int:
    score = 0
    for piece in board:
        if piece > 0:
            score += PIECE_VALUES[piece_type(piece)]
        elif piece < 0:
            score -= PIECE_VALUES[piece_type(piece)]
    return score


def _find_king_square(board: tuple[int, ...], color: int) -> int:
    target = color * KING
    try:
        return board.index(target)
    except ValueError as exc:
        raise ChessError(f"Missing {'white' if color == WHITE else 'black'} king") from exc


def _is_square_attacked_on_board(board: Sequence[int], square_index: int, by_color: int) -> bool:
    """Return whether ``by_color`` attacks ``square_index`` on ``board``.

    This helper is deliberately independent from ``Position`` construction.
    Legality filtering and move ordering call it on transient board lists to
    avoid allocating full child positions for queries that only need attack
    information.
    """

    target_file = file_of(square_index)
    target_rank = rank_of(square_index)

    pawn = by_color * PAWN
    pawn_sources = WHITE_PAWN_ATTACKERS[square_index] if by_color == WHITE else BLACK_PAWN_ATTACKERS[square_index]
    for source in pawn_sources:
        if board[source] == pawn:
            return True

    knight = by_color * KNIGHT
    for source in KNIGHT_ATTACKS[square_index]:
        if board[source] == knight:
            return True

    king = by_color * KING
    for source in KING_ATTACKS[square_index]:
        if board[source] == king:
            return True

    bishop = by_color * BISHOP
    rook = by_color * ROOK
    queen = by_color * QUEEN
    for df, dr in BISHOP_DIRECTIONS:
        file_index = target_file + df
        rank_index = target_rank + dr
        while on_board(file_index, rank_index):
            piece = board[square(file_index, rank_index)]
            if piece:
                if piece in (bishop, queen):
                    return True
                break
            file_index += df
            rank_index += dr
    for df, dr in ROOK_DIRECTIONS:
        file_index = target_file + df
        rank_index = target_rank + dr
        while on_board(file_index, rank_index):
            piece = board[square(file_index, rank_index)]
            if piece:
                if piece in (rook, queen):
                    return True
                break
            file_index += df
            rank_index += dr
    return False


@dataclass(frozen=True, slots=True)
class Position:
    """Immutable chess position with fully controlled transitions."""

    board: tuple[int, ...]
    turn: int = WHITE
    castling: int = ALL_CASTLING
    ep_square: int = NO_SQUARE
    halfmove_clock: int = 0
    fullmove_number: int = 1
    zobrist_hash: int = 0
    history: tuple[int, ...] = ()
    white_king_square: int = NO_SQUARE
    black_king_square: int = NO_SQUARE
    material_balance: int = 0

    def __post_init__(self) -> None:
        if len(self.board) != 64:
            raise ChessError(f"Board must contain 64 squares, got {len(self.board)}")
        if self.turn not in (WHITE, BLACK):
            raise ChessError(f"Invalid side to move: {self.turn}")
        if self.castling != (self.castling & ALL_CASTLING):
            raise ChessError(f"Invalid castling bitmask: {self.castling}")
        if self.ep_square != NO_SQUARE and not 0 <= self.ep_square < 64:
            raise ChessError(f"Invalid en-passant square: {self.ep_square}")
        if self.halfmove_clock < 0:
            raise ChessError("Halfmove clock cannot be negative")
        if self.fullmove_number < 1:
            raise ChessError("Fullmove number must be at least 1")
        white_kings = self.board.count(WHITE * KING)
        black_kings = self.board.count(BLACK * KING)
        if white_kings != 1 or black_kings != 1:
            raise ChessError(
                f"A legal position needs exactly one king per side, got white={white_kings}, black={black_kings}"
            )
        white_king_square = _find_king_square(self.board, WHITE)
        black_king_square = _find_king_square(self.board, BLACK)
        if self.white_king_square != white_king_square:
            object.__setattr__(self, "white_king_square", white_king_square)
        if self.black_king_square != black_king_square:
            object.__setattr__(self, "black_king_square", black_king_square)
        material_balance = _material_balance(self.board)
        if self.material_balance != material_balance:
            object.__setattr__(self, "material_balance", material_balance)
        zobrist = compute_zobrist_hash(self.board, self.turn, self.castling, self.ep_square)
        if self.zobrist_hash != zobrist:
            object.__setattr__(self, "zobrist_hash", zobrist)
        if not self.history:
            object.__setattr__(self, "history", (zobrist,))

    @classmethod
    def starting(cls) -> "Position":
        return cls.from_fen(STARTING_FEN)

    @classmethod
    def from_fen(cls, fen: str) -> "Position":
        fields = fen.strip().split()
        if len(fields) != 6:
            raise ChessError(f"FEN must contain 6 fields: {fen!r}")
        placement, turn_text, castling_text, ep_text, halfmove_text, fullmove_text = fields
        board = [EMPTY] * 64
        ranks = placement.split("/")
        if len(ranks) != 8:
            raise ChessError(f"FEN placement must contain 8 ranks: {placement!r}")
        for fen_rank, rank_text in enumerate(ranks):
            rank_index = 7 - fen_rank
            file_index = 0
            for char in rank_text:
                if char.isdigit():
                    empty_count = int(char)
                    if not 1 <= empty_count <= 8:
                        raise ChessError(f"Invalid empty count in FEN: {char!r}")
                    file_index += empty_count
                elif char in CHAR_TO_PIECE:
                    if file_index >= 8:
                        raise ChessError(f"Too many squares in FEN rank: {rank_text!r}")
                    board[square(file_index, rank_index)] = CHAR_TO_PIECE[char]
                    file_index += 1
                else:
                    raise ChessError(f"Invalid piece character in FEN: {char!r}")
            if file_index != 8:
                raise ChessError(f"FEN rank does not contain 8 squares: {rank_text!r}")
        if turn_text == "w":
            turn = WHITE
        elif turn_text == "b":
            turn = BLACK
        else:
            raise ChessError(f"Invalid side-to-move field in FEN: {turn_text!r}")
        castling = text_to_castling(castling_text)
        ep_square = NO_SQUARE if ep_text == "-" else parse_square(ep_text)
        try:
            halfmove_clock = int(halfmove_text)
            fullmove_number = int(fullmove_text)
        except ValueError as exc:
            raise ChessError(f"Invalid FEN move counters: {halfmove_text!r} {fullmove_text!r}") from exc
        if halfmove_clock < 0 or fullmove_number < 1:
            raise ChessError("FEN counters must be non-negative halfmove and positive fullmove")
        board_tuple = tuple(board)
        zobrist = compute_zobrist_hash(board_tuple, turn, castling, ep_square)
        return cls(
            board=board_tuple,
            turn=turn,
            castling=castling,
            ep_square=ep_square,
            halfmove_clock=halfmove_clock,
            fullmove_number=fullmove_number,
            zobrist_hash=zobrist,
            history=(zobrist,),
        )

    @classmethod
    def _trusted(
        cls,
        *,
        board: tuple[int, ...],
        turn: int,
        castling: int,
        ep_square: int,
        halfmove_clock: int,
        fullmove_number: int,
        zobrist_hash: int,
        history: tuple[int, ...],
        white_king_square: int = NO_SQUARE,
        black_king_square: int = NO_SQUARE,
        material_balance: int | None = None,
    ) -> "Position":
        position = object.__new__(cls)
        object.__setattr__(position, "board", board)
        object.__setattr__(position, "turn", turn)
        object.__setattr__(position, "castling", castling)
        object.__setattr__(position, "ep_square", ep_square)
        object.__setattr__(position, "halfmove_clock", halfmove_clock)
        object.__setattr__(position, "fullmove_number", fullmove_number)
        object.__setattr__(position, "zobrist_hash", zobrist_hash)
        object.__setattr__(position, "history", history)
        object.__setattr__(
            position,
            "white_king_square",
            _find_king_square(board, WHITE) if white_king_square == NO_SQUARE else white_king_square,
        )
        object.__setattr__(
            position,
            "black_king_square",
            _find_king_square(board, BLACK) if black_king_square == NO_SQUARE else black_king_square,
        )
        object.__setattr__(
            position,
            "material_balance",
            _material_balance(board) if material_balance is None else material_balance,
        )
        return position

    def to_fen(self) -> str:
        rank_texts: list[str] = []
        for rank_index in range(7, -1, -1):
            empties = 0
            parts: list[str] = []
            for file_index in range(8):
                piece = self.board[square(file_index, rank_index)]
                if piece == EMPTY:
                    empties += 1
                else:
                    if empties:
                        parts.append(str(empties))
                        empties = 0
                    parts.append(PIECE_TO_CHAR[piece])
            if empties:
                parts.append(str(empties))
            rank_texts.append("".join(parts))
        turn_text = "w" if self.turn == WHITE else "b"
        ep_text = "-" if self.ep_square == NO_SQUARE else square_name(self.ep_square)
        return (
            f"{'/'.join(rank_texts)} {turn_text} {castling_to_text(self.castling)} "
            f"{ep_text} {self.halfmove_clock} {self.fullmove_number}"
        )

    def pretty(self) -> str:
        lines: list[str] = []
        for rank_index in range(7, -1, -1):
            row = [PIECE_TO_CHAR[self.board[square(file_index, rank_index)]] for file_index in range(8)]
            lines.append(f"{rank_index + 1}  " + " ".join(row))
        lines.append("")
        lines.append("   a b c d e f g h")
        lines.append(f"Turn: {'White' if self.turn == WHITE else 'Black'}")
        lines.append(
            "State: "
            f"castling={castling_to_text(self.castling)} "
            f"ep={'-' if self.ep_square == NO_SQUARE else square_name(self.ep_square)} "
            f"halfmove={self.halfmove_clock} fullmove={self.fullmove_number}"
        )
        return "\n".join(lines)

    def piece_at(self, square_index: int) -> int:
        if not 0 <= square_index < 64:
            raise ChessError(f"Square out of range: {square_index}")
        return self.board[square_index]

    def king_square(self, color: int) -> int:
        if color == WHITE:
            return self.white_king_square
        if color == BLACK:
            return self.black_king_square
        raise ChessError(f"Invalid king color: {color}")

    def is_in_check(self, color: int | None = None) -> bool:
        side = self.turn if color is None else color
        return self.is_square_attacked(self.king_square(side), opponent(side))

    def is_square_attacked(self, square_index: int, by_color: int) -> bool:
        return _is_square_attacked_on_board(self.board, square_index, by_color)

    def generate_pseudo_legal_moves(self, color: int | None = None) -> Iterator[Move]:
        side = self.turn if color is None else color
        for from_sq, piece in enumerate(self.board):
            if piece == EMPTY or color_of(piece) != side:
                continue
            kind = piece_type(piece)
            if kind == PAWN:
                yield from self._pawn_moves(from_sq, side)
            elif kind == KNIGHT:
                yield from self._jump_attack_table_moves(from_sq, side, KNIGHT_ATTACKS)
            elif kind == BISHOP:
                yield from self._slide_moves(from_sq, side, BISHOP_DIRECTIONS)
            elif kind == ROOK:
                yield from self._slide_moves(from_sq, side, ROOK_DIRECTIONS)
            elif kind == QUEEN:
                yield from self._slide_moves(from_sq, side, QUEEN_DIRECTIONS)
            elif kind == KING:
                yield from self._king_moves(from_sq, side)

    def legal_moves(self) -> list[Move]:
        side = self.turn
        own_king = self.king_square(side)
        moves: list[Move] = []
        for move in self.generate_pseudo_legal_moves(side):
            if self._is_legal_pseudo_move(move, side, own_king):
                moves.append(move)
        return moves

    def legal_captures_and_promotions(self) -> list[Move]:
        return [move for move in self.legal_moves() if self.is_capture(move) or move.promotion]

    def _pawn_moves(self, from_sq: int, side: int) -> Iterator[Move]:
        file_index = file_of(from_sq)
        rank_index = rank_of(from_sq)
        direction = 1 if side == WHITE else -1
        start_rank = 1 if side == WHITE else 6
        promotion_rank = 7 if side == WHITE else 0

        one_rank = rank_index + direction
        if on_board(file_index, one_rank):
            one_sq = square(file_index, one_rank)
            if self.board[one_sq] == EMPTY:
                if one_rank == promotion_rank:
                    for promotion in PROMOTION_PIECES:
                        yield Move(from_sq, one_sq, promotion=promotion)
                else:
                    yield Move(from_sq, one_sq)
                    two_rank = rank_index + 2 * direction
                    if rank_index == start_rank and on_board(file_index, two_rank):
                        two_sq = square(file_index, two_rank)
                        if self.board[two_sq] == EMPTY:
                            yield Move(from_sq, two_sq)

        for df in (-1, 1):
            target_file = file_index + df
            target_rank = rank_index + direction
            if not on_board(target_file, target_rank):
                continue
            to_sq = square(target_file, target_rank)
            target = self.board[to_sq]
            if target != EMPTY and color_of(target) == opponent(side) and piece_type(target) != KING:
                if target_rank == promotion_rank:
                    for promotion in PROMOTION_PIECES:
                        yield Move(from_sq, to_sq, promotion=promotion)
                else:
                    yield Move(from_sq, to_sq)
            if to_sq == self.ep_square:
                captured_sq = to_sq - 8 if side == WHITE else to_sq + 8
                if 0 <= captured_sq < 64 and self.board[captured_sq] == opponent(side) * PAWN:
                    yield Move(from_sq, to_sq, is_en_passant=True)

    def _jump_attack_table_moves(self, from_sq: int, side: int, attacks: tuple[tuple[int, ...], ...]) -> Iterator[Move]:
        enemy = opponent(side)
        for to_sq in attacks[from_sq]:
            target = self.board[to_sq]
            if target == EMPTY or (color_of(target) == enemy and piece_type(target) != KING):
                yield Move(from_sq, to_sq)

    def _slide_moves(self, from_sq: int, side: int, directions: Iterable[tuple[int, int]]) -> Iterator[Move]:
        from_file = file_of(from_sq)
        from_rank = rank_of(from_sq)
        for df, dr in directions:
            target_file = from_file + df
            target_rank = from_rank + dr
            while on_board(target_file, target_rank):
                to_sq = square(target_file, target_rank)
                target = self.board[to_sq]
                if target == EMPTY:
                    yield Move(from_sq, to_sq)
                else:
                    if color_of(target) == opponent(side) and piece_type(target) != KING:
                        yield Move(from_sq, to_sq)
                    break
                target_file += df
                target_rank += dr

    def _king_moves(self, from_sq: int, side: int) -> Iterator[Move]:
        yield from self._jump_attack_table_moves(from_sq, side, KING_ATTACKS)
        if side == WHITE and from_sq == E1:
            if self._can_castle_kingside(WHITE):
                yield Move(E1, G1, is_castling=True)
            if self._can_castle_queenside(WHITE):
                yield Move(E1, C1, is_castling=True)
        elif side == BLACK and from_sq == E8:
            if self._can_castle_kingside(BLACK):
                yield Move(E8, G8, is_castling=True)
            if self._can_castle_queenside(BLACK):
                yield Move(E8, C8, is_castling=True)

    def _can_castle_kingside(self, side: int) -> bool:
        if side == WHITE:
            right, king_from, rook_from, through, to_sq = (
                WK_CASTLE,
                E1,
                H1,
                F1,
                G1,
            )
        else:
            right, king_from, rook_from, through, to_sq = (
                BK_CASTLE,
                E8,
                H8,
                F8,
                G8,
            )
        if not (self.castling & right):
            return False
        if self.board[king_from] != side * KING or self.board[rook_from] != side * ROOK:
            return False
        if self.board[through] != EMPTY or self.board[to_sq] != EMPTY:
            return False
        enemy = opponent(side)
        return not (
            self.is_square_attacked(king_from, enemy)
            or self.is_square_attacked(through, enemy)
            or self.is_square_attacked(to_sq, enemy)
        )

    def _can_castle_queenside(self, side: int) -> bool:
        if side == WHITE:
            right, king_from, rook_from, b_sq, through, to_sq = (
                WQ_CASTLE,
                E1,
                A1,
                B1,
                D1,
                C1,
            )
        else:
            right, king_from, rook_from, b_sq, through, to_sq = (
                BQ_CASTLE,
                E8,
                A8,
                B8,
                D8,
                C8,
            )
        if not (self.castling & right):
            return False
        if self.board[king_from] != side * KING or self.board[rook_from] != side * ROOK:
            return False
        if self.board[b_sq] != EMPTY or self.board[through] != EMPTY or self.board[to_sq] != EMPTY:
            return False
        enemy = opponent(side)
        return not (
            self.is_square_attacked(king_from, enemy)
            or self.is_square_attacked(through, enemy)
            or self.is_square_attacked(to_sq, enemy)
        )

    def make_move(self, move: Move, *, validate: bool = True, record_history: bool = True) -> "Position":
        actual_move = move
        if validate:
            for legal in self.legal_moves():
                if legal.uci() == move.uci():
                    actual_move = legal
                    break
            else:
                raise ChessError(f"Illegal move {move.uci()} in position {self.to_fen()}")
        return self._make_move_unchecked(actual_move, record_history=record_history, compute_hash=True)

    def _is_legal_pseudo_move(self, move: Move, side: int, own_king: int) -> bool:
        board, moving_piece, _captured_piece, _captured_square = self._apply_move_to_board(move)
        if color_of(moving_piece) != side:
            return False
        king_square_after = move.to_sq if piece_type(moving_piece) == KING else own_king
        return not _is_square_attacked_on_board(board, king_square_after, opponent(side))

    def gives_check(self, move: Move) -> bool:
        """Return whether a legal or pseudo-legal move gives check.

        Search move ordering uses this as a tactical hint.  It intentionally
        works on a transient board copy instead of constructing a child
        ``Position`` because only attack information is required.
        """

        board, moving_piece, _captured_piece, _captured_square = self._apply_move_to_board(move)
        side = color_of(moving_piece)
        return _is_square_attacked_on_board(board, self.king_square(opponent(side)), side)

    def parse_uci_move(self, text: str) -> Move:
        text = text.strip().lower()
        if len(text) not in (4, 5):
            raise ChessError(f"Invalid UCI move: {text!r}")
        try:
            from_sq = parse_square(text[:2])
            to_sq = parse_square(text[2:4])
        except ValueError as exc:
            raise ChessError(str(exc)) from exc
        promotion = 0
        if len(text) == 5:
            promotion = PROMOTION_CHARS.get(text[4], 0)
            if not promotion:
                raise ChessError(f"Invalid promotion piece in UCI move: {text!r}")
        requested = Move(from_sq, to_sq, promotion=promotion)
        for legal in self.legal_moves():
            if legal.uci() == requested.uci():
                return legal
        raise ChessError(f"Illegal move {text!r}")

    def _make_move_unchecked(
        self,
        move: Move,
        *,
        record_history: bool,
        compute_hash: bool = True,
    ) -> "Position":
        board, piece, captured_piece, captured_square = self._apply_move_to_board(move)
        side = color_of(piece)

        castling = self._updated_castling_rights(piece, move.from_sq, captured_piece, captured_square)
        ep_square = NO_SQUARE
        if piece_type(piece) == PAWN and abs(move.to_sq - move.from_sq) == 16:
            ep_square = (move.from_sq + move.to_sq) // 2

        is_capture = captured_piece != EMPTY
        halfmove_clock = 0 if piece_type(piece) == PAWN or is_capture else self.halfmove_clock + 1
        fullmove_number = self.fullmove_number + (1 if side == BLACK else 0)
        next_turn = opponent(side)
        board_tuple = tuple(board)
        white_king_square = self.white_king_square
        black_king_square = self.black_king_square
        if piece_type(piece) == KING:
            if side == WHITE:
                white_king_square = move.to_sq
            else:
                black_king_square = move.to_sq
        material_balance = self.material_balance
        if captured_piece:
            captured_value = PIECE_VALUES[piece_type(captured_piece)]
            material_balance += captured_value if color_of(captured_piece) == BLACK else -captured_value
        if move.promotion:
            promotion_delta = PIECE_VALUES[move.promotion] - PIECE_VALUES[PAWN]
            material_balance += promotion_delta if side == WHITE else -promotion_delta
        if record_history:
            compute_hash = True
        zobrist = compute_zobrist_hash(board_tuple, next_turn, castling, ep_square) if compute_hash else 0
        if record_history:
            history = self.history + (zobrist,)
        else:
            history = self.history
        return Position._trusted(
            board=board_tuple,
            turn=next_turn,
            castling=castling,
            ep_square=ep_square,
            halfmove_clock=halfmove_clock,
            fullmove_number=fullmove_number,
            zobrist_hash=zobrist,
            history=history,
            white_king_square=white_king_square,
            black_king_square=black_king_square,
            material_balance=material_balance,
        )

    def _apply_move_to_board(self, move: Move) -> tuple[list[int], int, int, int]:
        """Apply ``move`` to a mutable board copy and return capture metadata.

        The returned tuple is ``(board, moving_piece, captured_piece,
        captured_square)``.  Both the immutable transition path and the
        transient legality probes share this helper so special-move semantics
        stay centralized.
        """

        board = list(self.board)
        piece = board[move.from_sq]
        if piece == EMPTY:
            raise ChessError(f"Cannot move from empty square {square_name(move.from_sq)}")
        side = color_of(piece)
        captured_piece = board[move.to_sq]
        captured_square = move.to_sq

        board[move.from_sq] = EMPTY
        if move.is_en_passant:
            captured_square = move.to_sq - 8 if side == WHITE else move.to_sq + 8
            captured_piece = board[captured_square]
            if captured_piece != opponent(side) * PAWN:
                raise ChessError(f"Invalid en-passant capture on {square_name(move.to_sq)}")
            board[captured_square] = EMPTY

        placed_piece = side * move.promotion if move.promotion else piece
        board[move.to_sq] = placed_piece

        if move.is_castling:
            if side == WHITE and move.to_sq == G1:
                self._move_rook_for_castle(board, H1, F1, WHITE)
            elif side == WHITE and move.to_sq == C1:
                self._move_rook_for_castle(board, A1, D1, WHITE)
            elif side == BLACK and move.to_sq == G8:
                self._move_rook_for_castle(board, H8, F8, BLACK)
            elif side == BLACK and move.to_sq == C8:
                self._move_rook_for_castle(board, A8, D8, BLACK)
            else:
                raise ChessError(f"Invalid castling move: {move.uci()}")
        return board, piece, captured_piece, captured_square

    @staticmethod
    def _move_rook_for_castle(board: list[int], rook_from: int, rook_to: int, side: int) -> None:
        if board[rook_from] != side * ROOK:
            raise ChessError(f"Missing rook for castling on {square_name(rook_from)}")
        board[rook_from] = EMPTY
        board[rook_to] = side * ROOK

    def _updated_castling_rights(
        self,
        moving_piece: int,
        from_sq: int,
        captured_piece: int,
        captured_square: int,
    ) -> int:
        rights = self.castling
        side = color_of(moving_piece)
        if piece_type(moving_piece) == KING:
            rights &= ~(WK_CASTLE | WQ_CASTLE) if side == WHITE else ~(BK_CASTLE | BQ_CASTLE)
        elif piece_type(moving_piece) == ROOK:
            if from_sq == H1:
                rights &= ~WK_CASTLE
            elif from_sq == A1:
                rights &= ~WQ_CASTLE
            elif from_sq == H8:
                rights &= ~BK_CASTLE
            elif from_sq == A8:
                rights &= ~BQ_CASTLE

        if piece_type(captured_piece) == ROOK:
            if captured_square == H1:
                rights &= ~WK_CASTLE
            elif captured_square == A1:
                rights &= ~WQ_CASTLE
            elif captured_square == H8:
                rights &= ~BK_CASTLE
            elif captured_square == A8:
                rights &= ~BQ_CASTLE
        return rights & ALL_CASTLING

    def is_capture(self, move: Move) -> bool:
        return move.is_en_passant or self.board[move.to_sq] != EMPTY

    def move_score_hint(self, move: Move) -> int:
        """Fast tactical hint used by move ordering."""

        score = 0
        attacker = self.board[move.from_sq]
        victim = self.board[move.to_sq]
        if move.is_en_passant:
            victim = opponent(color_of(attacker)) * PAWN
        if victim:
            score += 10_000 + 10 * piece_type(victim) - piece_type(attacker)
        if move.promotion:
            score += 8_000 + 100 * move.promotion
        if move.is_castling:
            score += 50
        return score

    def repetition_count(self) -> int:
        return sum(1 for value in self.history if value == self.zobrist_hash)

    def is_threefold_repetition(self) -> bool:
        return self.repetition_count() >= 3

    def is_fifty_move_rule(self) -> bool:
        return self.halfmove_clock >= 100

    def is_insufficient_material(self) -> bool:
        pieces = [(sq, piece) for sq, piece in enumerate(self.board) if piece and piece_type(piece) != KING]
        if not pieces:
            return True
        if len(pieces) == 1:
            return piece_type(pieces[0][1]) in (BISHOP, KNIGHT)
        if all(piece_type(piece) == BISHOP for _sq, piece in pieces):
            colors = {(file_of(sq) + rank_of(sq)) & 1 for sq, _piece in pieces}
            return len(colors) == 1
        return False

    def status(self) -> GameStatus:
        moves = self.legal_moves()
        if not moves:
            if self.is_in_check(self.turn):
                return GameStatus("checkmate", winner=opponent(self.turn), reason="king is checkmated")
            return GameStatus("stalemate", reason="side to move has no legal moves")
        if self.is_threefold_repetition():
            return GameStatus("draw", reason="threefold repetition")
        if self.is_fifty_move_rule():
            return GameStatus("draw", reason="50-move rule")
        if self.is_insufficient_material():
            return GameStatus("draw", reason="insufficient mating material")
        if self.is_in_check(self.turn):
            return GameStatus("check", reason="king is in check")
        return GameStatus("active")


def parse_uci_move(text: str, position: Position) -> Move:
    return position.parse_uci_move(text)


def perft(position: Position, depth: int) -> int:
    if depth < 0:
        raise ChessError(f"Perft depth cannot be negative: {depth}")
    if depth == 0:
        return 1
    moves = position.legal_moves()
    if depth == 1:
        return len(moves)
    nodes = 0
    for move in moves:
        nodes += perft(position._make_move_unchecked(move, record_history=False, compute_hash=False), depth - 1)
    return nodes


def perft_divide(position: Position, depth: int) -> dict[str, int]:
    if depth < 1:
        raise ChessError("Perft divide depth must be at least 1")
    result: dict[str, int] = {}
    for move in position.legal_moves():
        result[move.uci()] = perft(
            position._make_move_unchecked(move, record_history=False, compute_hash=False), depth - 1
        )
    return dict(sorted(result.items()))
