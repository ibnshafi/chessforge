"""Deterministic alpha-beta chess search."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .constants import BISHOP, KNIGHT, PAWN, QUEEN, ROOK, WHITE, opponent, piece_type
from .core import GameStatus, Move, NO_SQUARE, Position, compute_zobrist_hash
from .evaluation import evaluate
from .metrics import DepthReport, SearchStats
from .tactics import static_exchange_evaluation

INF = 10_000_000
MATE_SCORE = 9_000_000
EXACT = 0
LOWER_BOUND = 1
UPPER_BOUND = 2


class SearchTimeout(RuntimeError):
    """Internal control-flow exception for soft time limits."""


@dataclass(frozen=True, slots=True)
class SearchConfig:
    max_depth: int = 4
    time_limit: float | None = 3.0
    use_quiescence: bool = True
    max_quiescence_depth: int = 8
    use_transposition_table: bool = True
    log: bool = False
    use_pvs: bool = True
    use_aspiration_windows: bool = True
    aspiration_window: int = 50
    use_killer_heuristic: bool = True
    use_history_heuristic: bool = True
    use_late_move_reductions: bool = True
    use_null_move_pruning: bool = True
    null_move_reduction: int = 2
    use_check_extensions: bool = True
    use_mate_distance_pruning: bool = True
    use_internal_iterative_deepening: bool = True
    use_see_ordering: bool = True
    transposition_table_size: int = 250_000


@dataclass(frozen=True, slots=True)
class SearchResult:
    best_move: Move | None
    score: int
    depth: int
    nodes: int
    elapsed: float
    principal_variation: tuple[Move, ...]
    stats: SearchStats = field(default_factory=SearchStats)
    depth_reports: tuple[DepthReport, ...] = ()


@dataclass(slots=True)
class TranspositionEntry:
    depth: int
    score: int
    flag: int
    best_move: Move | None
    generation: int = 0


class SearchEngine:
    """Classical negamax alpha-beta search with iterative deepening."""

    def __init__(self, evaluator: Callable[[Position], int] | None = None) -> None:
        self.table: dict[int, TranspositionEntry] = {}
        self.nodes = 0
        self.stats = SearchStats()
        self.depth_reports: list[DepthReport] = []
        self.killers: list[list[Move | None]] = []
        self.history: dict[tuple[int, int, int], int] = {}
        self.generation = 0
        self.evaluator = evaluator or evaluate
        self.deadline: float | None = None
        self.config = SearchConfig()

    def clear(self) -> None:
        self.table.clear()
        self.history.clear()

    def search(self, position: Position, config: SearchConfig | None = None) -> SearchResult:
        self.config = config or SearchConfig()
        if self.config.max_depth < 1:
            raise ValueError("Search depth must be at least 1")
        start = time.perf_counter()
        self.deadline = None if self.config.time_limit is None else start + self.config.time_limit
        self.nodes = 0
        self.stats = SearchStats()
        self.depth_reports = []
        self.killers = [[None, None] for _ in range(self.config.max_depth + self.config.max_quiescence_depth + 8)]
        self.generation += 1

        legal = position.legal_moves()
        self.stats.record_legal_batch(len(legal))
        if not legal:
            status = position.status()
            elapsed = time.perf_counter() - start
            return SearchResult(None, self._terminal_score(status, 0), 0, 0, elapsed, (), self.stats, ())

        ordered = self._ordered_moves(position, legal, None, 0)
        best_move = ordered[0]
        best_score = -INF
        completed_depth = 0
        best_pv: tuple[Move, ...] = (best_move,)
        previous_score = 0

        for depth in range(1, self.config.max_depth + 1):
            try:
                if self.config.use_aspiration_windows and depth >= 3 and completed_depth:
                    score, move = self._aspiration_root_search(position, depth, previous_score)
                else:
                    score, move = self._root_search(position, depth, -INF, INF)
            except SearchTimeout:
                break
            if move is not None:
                best_move = move
                best_score = score
                completed_depth = depth
                best_pv = self.principal_variation(position, depth)
                self.stats.depth_iterations += 1
                self.depth_reports.append(
                    DepthReport(
                        depth=depth,
                        score=best_score,
                        best_move=best_move.uci(),
                        nodes=self.nodes,
                        elapsed=time.perf_counter() - start,
                        principal_variation=tuple(move.uci() for move in best_pv),
                    )
                )
                previous_score = best_score
            if self.config.log:
                pv_text = " ".join(move.uci() for move in best_pv)
                print(f"info depth {depth} score cp {best_score} nodes {self.nodes} pv {pv_text}", flush=True)
            if abs(best_score) > MATE_SCORE - 1000:
                break

        elapsed = time.perf_counter() - start
        if completed_depth == 0:
            best_score = self._static_side_score(position)
        return SearchResult(
            best_move,
            best_score,
            completed_depth,
            self.nodes,
            elapsed,
            best_pv,
            self.stats,
            tuple(self.depth_reports),
        )

    def _aspiration_root_search(self, position: Position, depth: int, previous_score: int) -> tuple[int, Move | None]:
        window = self.config.aspiration_window
        alpha = max(-INF, previous_score - window)
        beta = min(INF, previous_score + window)
        while True:
            score, move = self._root_search(position, depth, alpha, beta)
            if score <= alpha:
                self.stats.aspiration_researches += 1
                alpha = -INF
            elif score >= beta:
                self.stats.aspiration_researches += 1
                beta = INF
            else:
                return score, move
            if alpha == -INF and beta == INF:
                return self._root_search(position, depth, alpha, beta)

    def _root_search(self, position: Position, depth: int, alpha: int, beta: int) -> tuple[int, Move | None]:
        original_alpha = alpha
        best_score = -INF
        best_move: Move | None = None
        tt_move = self.table.get(position.zobrist_hash).best_move if position.zobrist_hash in self.table else None
        moves = self._ordered_moves(position, position.legal_moves(), tt_move, 0)
        self.stats.record_legal_batch(len(moves))
        for index, move in enumerate(moves):
            child = position.make_move(move, validate=False, record_history=False)
            if self.config.use_pvs and index > 0:
                self.stats.pvs_searches += 1
                score = -self._negamax(child, depth - 1, -alpha - 1, -alpha, 1, allow_null=True)
                if alpha < score < beta:
                    self.stats.pvs_researches += 1
                    score = -self._negamax(child, depth - 1, -beta, -alpha, 1, allow_null=True)
            else:
                score = -self._negamax(child, depth - 1, -beta, -alpha, 1, allow_null=True)
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                self._record_beta_cutoff(position, move, depth, 0)
                break
        if self.config.use_transposition_table and best_move is not None:
            if best_score <= original_alpha:
                flag = UPPER_BOUND
            elif best_score >= beta:
                flag = LOWER_BOUND
            else:
                flag = EXACT
            self._store_tt(position.zobrist_hash, TranspositionEntry(depth, best_score, flag, best_move, self.generation))
        return best_score, best_move

    def _negamax(self, position: Position, depth: int, alpha: int, beta: int, ply: int, *, allow_null: bool) -> int:
        self._check_timeout()
        self._record_node(ply)

        if position.is_threefold_repetition() or position.is_fifty_move_rule() or position.is_insufficient_material():
            return 0

        if self.config.use_mate_distance_pruning:
            alpha = max(alpha, -MATE_SCORE + ply)
            beta = min(beta, MATE_SCORE - ply)
            if alpha >= beta:
                self.stats.mate_distance_prunes += 1
                return alpha

        original_alpha = alpha
        entry = None
        if self.config.use_transposition_table:
            self.stats.tt_probes += 1
            entry = self.table.get(position.zobrist_hash)
            if entry is not None:
                self.stats.tt_hits += 1
        if entry is not None and entry.depth >= depth:
            self.stats.tt_usable_hits += 1
            if entry.flag == EXACT:
                self.stats.tt_cutoffs += 1
                return entry.score
            if entry.flag == LOWER_BOUND:
                alpha = max(alpha, entry.score)
            elif entry.flag == UPPER_BOUND:
                beta = min(beta, entry.score)
            if alpha >= beta:
                self.stats.tt_cutoffs += 1
                return entry.score

        if depth == 0:
            if self.config.use_quiescence:
                return self._quiescence(position, alpha, beta, ply, 0)
            return self._static_side_score(position)

        in_check = position.is_in_check(position.turn)

        if (
            self.config.use_null_move_pruning
            and allow_null
            and depth >= 3
            and not in_check
            and beta < MATE_SCORE - 1000
            and self._has_null_move_material(position)
        ):
            reduction = self.config.null_move_reduction + (1 if depth >= 5 else 0)
            null_position = self._make_null_move(position)
            self.stats.null_move_searches += 1
            score = -self._negamax(
                null_position,
                max(0, depth - 1 - reduction),
                -beta,
                -beta + 1,
                ply + 1,
                allow_null=False,
            )
            if score >= beta:
                self.stats.null_move_prunes += 1
                return beta

        if self.config.use_internal_iterative_deepening and entry is None and depth >= 4 and not in_check:
            self.stats.iid_searches += 1
            self._negamax(position, depth - 2, alpha, beta, ply, allow_null=False)
            entry = self.table.get(position.zobrist_hash) if self.config.use_transposition_table else None

        legal = position.legal_moves()
        self.stats.record_legal_batch(len(legal))
        if not legal:
            if position.is_in_check(position.turn):
                return -MATE_SCORE + ply
            return 0

        best_move: Move | None = None
        best_score = -INF
        tt_move = entry.best_move if entry else None
        ordered = self._ordered_moves(position, legal, tt_move, ply)
        for move_index, move in enumerate(ordered):
            child = position.make_move(move, validate=False, record_history=False)
            gives_check = child.is_in_check(child.turn)
            extension = 0
            if self.config.use_check_extensions and gives_check:
                extension = 1
                self.stats.check_extensions += 1
            search_depth = depth - 1 + extension

            quiet = self._is_quiet(position, move)
            reduced = False
            if (
                self.config.use_late_move_reductions
                and move_index >= 4
                and depth >= 3
                and quiet
                and not in_check
                and not gives_check
            ):
                reduced = True
                self.stats.lmr_reductions += 1
                score = -self._negamax(
                    child,
                    max(0, search_depth - 1),
                    -alpha - 1,
                    -alpha,
                    ply + 1,
                    allow_null=True,
                )
            else:
                score = -INF

            if not reduced or score > alpha:
                if self.config.use_pvs and move_index > 0:
                    self.stats.pvs_searches += 1
                    score = -self._negamax(child, search_depth, -alpha - 1, -alpha, ply + 1, allow_null=True)
                    if alpha < score < beta:
                        self.stats.pvs_researches += 1
                        score = -self._negamax(child, search_depth, -beta, -alpha, ply + 1, allow_null=True)
                else:
                    score = -self._negamax(child, search_depth, -beta, -alpha, ply + 1, allow_null=True)
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                self._record_beta_cutoff(position, move, depth, ply)
                break

        if self.config.use_transposition_table:
            if best_score <= original_alpha:
                flag = UPPER_BOUND
            elif best_score >= beta:
                flag = LOWER_BOUND
            else:
                flag = EXACT
            self._store_tt(position.zobrist_hash, TranspositionEntry(depth, best_score, flag, best_move, self.generation))
        return best_score

    def _quiescence(self, position: Position, alpha: int, beta: int, ply: int, q_depth: int) -> int:
        self._check_timeout()
        self._record_node(ply, is_quiescence=True, q_depth=q_depth)
        stand_pat = self._static_side_score(position)
        if stand_pat >= beta:
            self.stats.stand_pat_cutoffs += 1
            return beta
        if alpha < stand_pat:
            alpha = stand_pat
        if q_depth >= self.config.max_quiescence_depth:
            return alpha

        moves = self._ordered_moves(position, position.legal_captures_and_promotions(), None, ply)
        self.stats.record_legal_batch(len(moves))
        for move in moves:
            child = position._make_move_unchecked(move, record_history=False, compute_hash=False)
            score = -self._quiescence(child, -beta, -alpha, ply + 1, q_depth + 1)
            if score >= beta:
                self.stats.q_beta_cutoffs += 1
                return beta
            if score > alpha:
                alpha = score
        return alpha

    def _ordered_moves(self, position: Position, moves: list[Move], tt_move: Move | None, ply: int) -> list[Move]:
        scored: list[tuple[int, Move]] = []
        self.stats.move_order_batches += 1
        self.stats.move_order_moves += len(moves)
        for move in moves:
            score = position.move_score_hint(move)
            if tt_move is not None and move == tt_move:
                score += 1_000_000
                self.stats.tt_move_order_hits += 1
            elif self.config.use_killer_heuristic and self._killer_match(move, ply):
                score += 40_000
                self.stats.killer_move_hits += 1
            if self.config.use_history_heuristic and self._is_quiet(position, move):
                history_score = self.history.get(self._history_key(position, move), 0)
                if history_score:
                    score += min(history_score, 30_000)
                    self.stats.history_move_hits += 1
            if self.config.use_see_ordering and position.is_capture(move):
                score += static_exchange_evaluation(position, move)
                self.stats.see_evaluations += 1
            if position.gives_check(move):
                score += 3_000
                self.stats.checking_moves_ordered += 1
            if position.is_capture(move) or move.promotion:
                self.stats.tactical_moves_ordered += 1
            scored.append((score, move))
        scored.sort(key=lambda item: (item[0], item[1].uci()), reverse=True)
        return [move for _score, move in scored]

    def _static_side_score(self, position: Position) -> int:
        sign = 1 if position.turn == WHITE else -1
        return sign * self.evaluator(position)

    def _terminal_score(self, status: GameStatus, ply: int) -> int:
        if status.state == "checkmate":
            return -MATE_SCORE + ply
        return 0

    def _check_timeout(self) -> None:
        if self.deadline is not None and (self.nodes & 2047) == 0:
            self.stats.timeout_checks += 1
            if time.perf_counter() >= self.deadline:
                raise SearchTimeout

    def _record_node(self, ply: int, *, is_quiescence: bool = False, q_depth: int = 0) -> None:
        self.nodes += 1
        self.stats.nodes += 1
        self.stats.max_ply = max(self.stats.max_ply, ply)
        if is_quiescence:
            self.stats.qnodes += 1
            self.stats.max_q_depth = max(self.stats.max_q_depth, q_depth)

    def _record_beta_cutoff(self, position: Position, move: Move, depth: int, ply: int) -> None:
        self.stats.beta_cutoffs += 1
        if not self._is_quiet(position, move):
            return
        if self.config.use_killer_heuristic and ply < len(self.killers):
            first, second = self.killers[ply]
            if move != first:
                self.killers[ply][1] = first if first != second else second
                self.killers[ply][0] = move
        if self.config.use_history_heuristic:
            key = self._history_key(position, move)
            self.history[key] = self.history.get(key, 0) + depth * depth

    def _is_quiet(self, position: Position, move: Move) -> bool:
        return not position.is_capture(move) and not move.promotion

    def _killer_match(self, move: Move, ply: int) -> bool:
        if ply >= len(self.killers):
            return False
        first, second = self.killers[ply]
        return move == first or move == second

    def _history_key(self, position: Position, move: Move) -> tuple[int, int, int]:
        return (position.board[move.from_sq], move.from_sq, move.to_sq)

    def _store_tt(self, key: int, entry: TranspositionEntry) -> None:
        if not self.config.use_transposition_table:
            return
        existing = self.table.get(key)
        if existing is not None and existing.depth > entry.depth and existing.generation == self.generation:
            return
        max_entries = max(1, self.config.transposition_table_size)
        if key not in self.table and len(self.table) >= max_entries:
            victim = min(self.table.items(), key=lambda item: (item[1].generation, item[1].depth, item[0]))[0]
            del self.table[victim]
        self.table[key] = entry
        self.stats.record_tt_store(entry.flag)

    def _has_null_move_material(self, position: Position) -> bool:
        tactical_material = {KNIGHT, BISHOP, ROOK, QUEEN}
        return any(
            piece * position.turn > 0 and piece_type(piece) in tactical_material
            for piece in position.board
        )

    def _make_null_move(self, position: Position) -> Position:
        next_turn = opponent(position.turn)
        fullmove_number = position.fullmove_number + (1 if position.turn == -1 else 0)
        zobrist = compute_zobrist_hash(position.board, next_turn, position.castling, NO_SQUARE)
        return Position._trusted(
            board=position.board,
            turn=next_turn,
            castling=position.castling,
            ep_square=NO_SQUARE,
            halfmove_clock=position.halfmove_clock + 1,
            fullmove_number=fullmove_number,
            zobrist_hash=zobrist,
            history=position.history,
            white_king_square=position.white_king_square,
            black_king_square=position.black_king_square,
            material_balance=position.material_balance,
        )

    def principal_variation(self, position: Position, depth: int) -> tuple[Move, ...]:
        pv: list[Move] = []
        current = position
        seen: set[int] = set()
        for _ in range(depth):
            if current.zobrist_hash in seen:
                break
            seen.add(current.zobrist_hash)
            entry = self.table.get(current.zobrist_hash)
            if entry is None or entry.best_move is None:
                break
            legal_by_uci = {move.uci(): move for move in current.legal_moves()}
            move = legal_by_uci.get(entry.best_move.uci())
            if move is None:
                break
            pv.append(move)
            current = current.make_move(move, validate=False, record_history=False)
        return tuple(pv)
