"""Text and data visualizations for engine internals."""

from __future__ import annotations

from .bitboards import BitboardView, iter_bits
from .constants import WHITE, color_of, parse_square, piece_type, square, square_name
from .core import Position
from .evaluation import evaluate
from .search import SearchConfig, SearchEngine


def board_grid(values: dict[int, str], default: str = ".") -> str:
    lines: list[str] = []
    for rank_index in range(7, -1, -1):
        row = [values.get(square(file_index, rank_index), default) for file_index in range(8)]
        lines.append(" ".join(row))
    return "\n".join(lines)


def attack_map(position: Position, color: int) -> dict[str, int]:
    view = BitboardView.from_position(position)
    attacks = view.all_attacks(position, color)
    return {square_name(sq): 1 for sq in iter_bits(attacks)}


def attack_map_text(position: Position, color: int) -> str:
    attacked = {parse_square(name): "*" for name in attack_map(position, color)}
    return board_grid(attacked)


def evaluation_heatmap(position: Position) -> dict[str, int]:
    base = evaluate(position)
    heatmap: dict[str, int] = {}
    for from_sq, piece in enumerate(position.board):
        if piece == 0 or color_of(piece) != position.turn or piece_type(piece) == 6:
            continue
        for move in position.legal_moves():
            if move.from_sq != from_sq:
                continue
            child = position.make_move(move, validate=False, record_history=False)
            sign = 1 if position.turn == WHITE else -1
            heatmap[move.uci()] = sign * (evaluate(child) - base)
    return dict(sorted(heatmap.items()))


def principal_variation_report(position: Position, depth: int) -> dict[str, object]:
    engine = SearchEngine()
    result = engine.search(position, SearchConfig(max_depth=depth, time_limit=None))
    return {
        "best_move": result.best_move.uci() if result.best_move else "0000",
        "score": result.score,
        "nodes": result.nodes,
        "pv": [move.uci() for move in result.principal_variation],
        "stats": result.stats.to_dict(),
        "depth_reports": [report.to_dict() for report in result.depth_reports],
    }


def move_ordering_snapshot(position: Position, depth: int = 1) -> list[dict[str, object]]:
    engine = SearchEngine()
    result = engine.search(position, SearchConfig(max_depth=depth, time_limit=None))
    legal = position.legal_moves()
    ordered = engine._ordered_moves(position, legal, result.best_move, 0)
    return [
        {
            "rank": index + 1,
            "move": move.uci(),
            "is_capture": position.is_capture(move),
            "gives_check": position.gives_check(move),
        }
        for index, move in enumerate(ordered)
    ]
