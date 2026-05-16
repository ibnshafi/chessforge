"""Run a short deterministic AI-vs-AI sample game."""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chessforge.core import Position
from chessforge.search import SearchConfig, SearchEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic ChessForge AI-vs-AI sample.")
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--time", type=float, default=0.5)
    parser.add_argument("--max-plies", type=int, default=40)
    args = parser.parse_args()

    position = Position.starting()
    engine = SearchEngine()
    moves: list[str] = []
    for _ply in range(args.max_plies):
        status = position.status()
        if status.is_terminal:
            print(position.pretty())
            print(f"Game over: {status.state} {status.reason}")
            break
        result = engine.search(position, SearchConfig(max_depth=args.depth, time_limit=args.time))
        if result.best_move is None:
            break
        moves.append(result.best_move.uci())
        position = position.make_move(result.best_move)
    print(" ".join(moves))
    print(position.to_fen())


if __name__ == "__main__":
    main()
