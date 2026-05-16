"""Research tooling for deterministic engine experiments."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from .core import Position
from .search import SearchConfig, SearchEngine


@dataclass(frozen=True, slots=True)
class EngineSpec:
    name: str
    config: SearchConfig


@dataclass(frozen=True, slots=True)
class GameRecord:
    white: str
    black: str
    result: float
    plies: int
    final_fen: str
    moves: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "white": self.white,
            "black": self.black,
            "result": self.result,
            "plies": self.plies,
            "final_fen": self.final_fen,
            "moves": list(self.moves),
        }


def play_game(white: EngineSpec, black: EngineSpec, start_fen: str, max_plies: int) -> GameRecord:
    position = Position.from_fen(start_fen)
    engines = {1: SearchEngine(), -1: SearchEngine()}
    specs = {1: white, -1: black}
    moves: list[str] = []
    for _ply in range(max_plies):
        status = position.status()
        if status.is_terminal:
            break
        spec = specs[position.turn]
        result = engines[position.turn].search(position, spec.config)
        if result.best_move is None:
            break
        moves.append(result.best_move.uci())
        position = position.make_move(result.best_move)
    status = position.status()
    if status.state == "checkmate":
        score = 1.0 if status.winner == 1 else 0.0
    else:
        score = 0.5
    return GameRecord(white.name, black.name, score, len(moves), position.to_fen(), tuple(moves))


def round_robin(specs: list[EngineSpec], start_fens: list[str], max_plies: int) -> list[GameRecord]:
    records: list[GameRecord] = []
    for white, black in itertools.permutations(specs, 2):
        for fen in start_fens:
            records.append(play_game(white, black, fen, max_plies))
    return records


def score_rate(records: list[GameRecord], engine_name: str) -> float:
    score = 0.0
    games = 0
    for record in records:
        if record.white == engine_name:
            score += record.result
            games += 1
        elif record.black == engine_name:
            score += 1.0 - record.result
            games += 1
    return score / games if games else 0.0


def elo_from_score(score: float) -> float:
    score = min(0.999, max(0.001, score))
    return -400.0 * math.log10(1.0 / score - 1.0)


def sprt_log_likelihood(results: list[float], elo0: float, elo1: float) -> float:
    def expected(elo: float) -> float:
        return 1.0 / (1.0 + 10.0 ** (-elo / 400.0))

    p0 = expected(elo0)
    p1 = expected(elo1)
    llr = 0.0
    for result in results:
        if result == 1.0:
            llr += math.log(p1 / p0)
        elif result == 0.0:
            llr += math.log((1.0 - p1) / (1.0 - p0))
        else:
            draw0 = 2.0 * math.sqrt(p0 * (1.0 - p0))
            draw1 = 2.0 * math.sqrt(p1 * (1.0 - p1))
            llr += math.log(max(1e-9, draw1) / max(1e-9, draw0))
    return llr


def search_ablation_specs(depth: int) -> list[EngineSpec]:
    base = SearchConfig(max_depth=depth, time_limit=None)
    return [
        EngineSpec("modern", base),
        EngineSpec("no_pvs", SearchConfig(max_depth=depth, time_limit=None, use_pvs=False)),
        EngineSpec("no_null", SearchConfig(max_depth=depth, time_limit=None, use_null_move_pruning=False)),
        EngineSpec("no_lmr", SearchConfig(max_depth=depth, time_limit=None, use_late_move_reductions=False)),
        EngineSpec("no_history", SearchConfig(max_depth=depth, time_limit=None, use_history_heuristic=False)),
    ]


def parameter_sweep(start_fen: str, depths: list[int], max_plies: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for depth in depths:
        specs = search_ablation_specs(depth)
        records = round_robin(specs, [start_fen], max_plies)
        for spec in specs:
            rate = score_rate(records, spec.name)
            rows.append(
                {
                    "engine": spec.name,
                    "depth": depth,
                    "games": sum(1 for record in records if record.white == spec.name or record.black == spec.name),
                    "score_rate": rate,
                    "elo": elo_from_score(rate),
                }
            )
    return rows

