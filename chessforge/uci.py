"""Minimal UCI protocol loop for engine integration."""

from __future__ import annotations

import sys

from .core import ChessError, Position
from .search import SearchConfig, SearchEngine


def _position_from_command(tokens: list[str], current: Position) -> Position:
    if not tokens:
        return current
    index = 0
    if tokens[index] == "startpos":
        position = Position.starting()
        index += 1
    elif tokens[index] == "fen":
        index += 1
        fen_parts: list[str] = []
        while index < len(tokens) and tokens[index] != "moves":
            fen_parts.append(tokens[index])
            index += 1
        if len(fen_parts) != 6:
            raise ChessError("UCI position fen requires a full six-field FEN")
        position = Position.from_fen(" ".join(fen_parts))
    else:
        raise ChessError(f"Unknown position command: {' '.join(tokens)}")

    if index < len(tokens) and tokens[index] == "moves":
        index += 1
        while index < len(tokens):
            move = position.parse_uci_move(tokens[index])
            position = position.make_move(move)
            index += 1
    return position


def _config_from_go(tokens: list[str]) -> SearchConfig:
    depth = 4
    time_limit = 3.0
    if "depth" in tokens:
        idx = tokens.index("depth")
        if idx + 1 < len(tokens):
            depth = max(1, int(tokens[idx + 1]))
            time_limit = None
    if "movetime" in tokens:
        idx = tokens.index("movetime")
        if idx + 1 < len(tokens):
            time_limit = max(0.001, int(tokens[idx + 1]) / 1000.0)
    return SearchConfig(max_depth=depth, time_limit=time_limit, log=True)


def main() -> int:
    position = Position.starting()
    engine = SearchEngine()
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        tokens = line.split()
        command = tokens[0]
        try:
            if command == "uci":
                print("id name ChessForge 0.1")
                print("id author ChessForge")
                print("option name Depth type spin default 4 min 1 max 64")
                print("uciok", flush=True)
            elif command == "isready":
                print("readyok", flush=True)
            elif command == "ucinewgame":
                position = Position.starting()
                engine.clear()
            elif command == "position":
                position = _position_from_command(tokens[1:], position)
            elif command == "go":
                result = engine.search(position, _config_from_go(tokens[1:]))
                best = result.best_move.uci() if result.best_move else "0000"
                print(f"bestmove {best}", flush=True)
            elif command == "stop":
                print("bestmove 0000", flush=True)
            elif command == "d":
                print(position.pretty(), flush=True)
            elif command == "quit":
                return 0
        except Exception as exc:
            print(f"info string error {type(exc).__name__}: {exc}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
