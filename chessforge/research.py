"""Command-line research experiments for ChessForge."""

from __future__ import annotations

import argparse
from pathlib import Path

from .benchmark import BENCHMARK_SUITE, write_csv, write_json
from .experiments import parameter_sweep


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic ChessForge research experiments.")
    parser.add_argument("--depths", default="1,2", help="comma-separated search depths")
    parser.add_argument("--max-plies", type=int, default=8)
    parser.add_argument("--fen", default=BENCHMARK_SUITE[0].fen)
    parser.add_argument("--json", type=Path, default=Path("benchmarks/research.json"))
    parser.add_argument("--csv", type=Path, default=Path("benchmarks/research.csv"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    depths = [int(part) for part in args.depths.split(",") if part.strip()]
    records = parameter_sweep(args.fen, depths, args.max_plies)
    write_json(records, args.json)
    write_csv(records, args.csv)
    print(f"wrote {len(records)} research records to {args.json} and {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

