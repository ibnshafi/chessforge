"""Playable command-line interface for ChessForge."""

from __future__ import annotations

import argparse
import sys

from .constants import BLACK, WHITE, opponent
from .core import ChessError, Position, perft, perft_divide
from .evaluation import evaluate
from .search import SearchConfig, SearchEngine


def _side_name(color: int) -> str:
    return "White" if color == WHITE else "Black"


def _print_help() -> None:
    print(
        "\nCommands:\n"
        "  e2e4        play a UCI move; promotions use e7e8q/e7e8n\n"
        "  legal       list legal moves\n"
        "  fen         print current FEN\n"
        "  board       print board\n"
        "  eval        print static evaluation\n"
        "  perft N     run perft at depth N from current position\n"
        "  divide N    run perft divide at depth N\n"
        "  undo        undo one ply\n"
        "  quit        exit\n"
    )


def _print_status(position: Position) -> None:
    status = position.status()
    if status.state == "active":
        print(f"{_side_name(position.turn)} to move.")
    elif status.state == "check":
        print(f"{_side_name(position.turn)} to move, in check.")
    elif status.state == "checkmate":
        print(f"Checkmate. {_side_name(status.winner or opponent(position.turn))} wins.")
    elif status.state == "stalemate":
        print("Stalemate.")
    else:
        print(f"Draw: {status.reason}.")


def _apply_human_command(command: str, stack: list[Position]) -> bool:
    position = stack[-1]
    parts = command.strip().split()
    if not parts:
        return True
    head = parts[0].lower()
    if head in {"quit", "exit"}:
        return False
    if head == "help":
        _print_help()
        return True
    if head == "board":
        print(position.pretty())
        return True
    if head == "fen":
        print(position.to_fen())
        return True
    if head == "legal":
        print(" ".join(move.uci() for move in position.legal_moves()))
        return True
    if head == "eval":
        score = evaluate(position)
        print(f"Static evaluation: {score:+d} cp (positive favors White)")
        return True
    if head == "perft":
        if len(parts) != 2 or not parts[1].isdigit():
            print("Usage: perft N")
            return True
        depth = int(parts[1])
        print(perft(position, depth))
        return True
    if head == "divide":
        if len(parts) != 2 or not parts[1].isdigit():
            print("Usage: divide N")
            return True
        depth = int(parts[1])
        for move, nodes in perft_divide(position, depth).items():
            print(f"{move}: {nodes}")
        return True
    if head == "undo":
        if len(stack) > 1:
            stack.pop()
            print(stack[-1].pretty())
        else:
            print("No move to undo.")
        return True

    try:
        move = position.parse_uci_move(head)
        stack.append(position.make_move(move))
        print(f"{_side_name(position.turn)} played {move.uci()}")
        print(stack[-1].pretty())
        _print_status(stack[-1])
    except ChessError as exc:
        print(f"Invalid command or move: {exc}")
    return True


def _search_move(engine: SearchEngine, position: Position, depth: int, time_limit: float | None) -> Position:
    config = SearchConfig(max_depth=depth, time_limit=time_limit)
    result = engine.search(position, config)
    if result.best_move is None:
        return position
    pv = " ".join(move.uci() for move in result.principal_variation)
    print(
        f"{_side_name(position.turn)} AI plays {result.best_move.uci()} "
        f"(depth {result.depth}, score {result.score:+d}, nodes {result.nodes}, pv {pv})"
    )
    return position.make_move(result.best_move)


def _run_interactive(args: argparse.Namespace) -> int:
    try:
        start = Position.from_fen(args.fen) if args.fen else Position.starting()
    except ChessError as exc:
        print(f"Invalid start position: {exc}", file=sys.stderr)
        return 2
    stack = [start]
    engine = SearchEngine()

    if args.mode == "human-human":
        human_sides = {WHITE, BLACK}
    elif args.mode == "human-ai":
        human_color = WHITE if args.human_color == "white" else BLACK
        human_sides = {human_color}
    else:
        human_sides = set()

    print(stack[-1].pretty())
    _print_status(stack[-1])
    if human_sides:
        _print_help()

    plies = 0
    while True:
        position = stack[-1]
        status = position.status()
        if status.is_terminal:
            _print_status(position)
            return 0
        if args.max_plies is not None and plies >= args.max_plies:
            print(f"Reached max plies ({args.max_plies}).")
            return 0

        if position.turn not in human_sides:
            next_position = _search_move(engine, position, args.depth, args.time)
            if next_position == position:
                _print_status(position)
                return 0
            stack.append(next_position)
            print(stack[-1].pretty())
            _print_status(stack[-1])
            plies += 1
            continue

        try:
            command = input(f"{_side_name(position.turn)}> ")
        except EOFError:
            print()
            return 0
        before = len(stack)
        if not _apply_human_command(command, stack):
            return 0
        if len(stack) > before:
            plies += 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ChessForge playable CLI")
    parser.add_argument(
        "--mode",
        choices=("human-human", "human-ai", "ai-ai"),
        default="human-ai",
        help="play mode",
    )
    parser.add_argument("--human-color", choices=("white", "black"), default="white")
    parser.add_argument("--depth", type=int, default=3, help="AI search depth")
    parser.add_argument("--time", type=float, default=2.0, help="soft AI time limit in seconds")
    parser.add_argument("--fen", default="", help="start from a FEN position")
    parser.add_argument("--max-plies", type=int, default=None, help="stop AI-vs-AI after this many plies")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return _run_interactive(args)


if __name__ == "__main__":
    raise SystemExit(main())
