"""Reproducible benchmark and experiment runner for ChessForge.

The benchmark layer uses only public engine APIs.  That keeps measurement code
honest: if a benchmark needs private state, the engine API is missing an
observability feature.  Records are plain dictionaries so JSON/CSV exports are
stable, diffable, and easy to process in notebooks or external dashboards.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .core import Position, perft
from .evaluation import evaluate
from .search import SearchConfig, SearchEngine


@dataclass(frozen=True, slots=True)
class BenchmarkPosition:
    name: str
    fen: str
    perft_depth: int
    search_depth: int


BENCHMARK_SUITE: tuple[BenchmarkPosition, ...] = (
    BenchmarkPosition(
        "startpos",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        4,
        4,
    ),
    BenchmarkPosition(
        "kiwipete",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        3,
        3,
    ),
    BenchmarkPosition(
        "ep_endgame",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        4,
        4,
    ),
    BenchmarkPosition(
        "tactical_pressure",
        "r2q1rk1/ppp2ppp/2n1bn2/3pp3/1b1PP3/2N1BN2/PPP1BPPP/R2Q1RK1 w - - 0 8",
        3,
        4,
    ),
)


def _timed_with_memory(fn: Callable[[], object]) -> tuple[object, float, int]:
    tracemalloc.start()
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, elapsed, peak


def _summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"best": 0.0, "median": 0.0, "mean": 0.0}
    return {
        "best": min(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
    }


def run_perft_benchmarks(positions: Iterable[BenchmarkPosition], repeats: int) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for bench in positions:
        elapsed_samples: list[float] = []
        memory_samples: list[int] = []
        nodes = 0
        for sample in range(repeats):
            position = Position.from_fen(bench.fen)
            result, elapsed, peak = _timed_with_memory(lambda: perft(position, bench.perft_depth))
            nodes = int(result)
            elapsed_samples.append(elapsed)
            memory_samples.append(peak)
            records.append(
                {
                    "kind": "perft_sample",
                    "position": bench.name,
                    "depth": bench.perft_depth,
                    "sample": sample,
                    "nodes": nodes,
                    "elapsed": elapsed,
                    "nps": nodes / elapsed if elapsed else 0.0,
                    "peak_memory_bytes": peak,
                }
            )
        times = _summary(elapsed_samples)
        records.append(
            {
                "kind": "perft_summary",
                "position": bench.name,
                "depth": bench.perft_depth,
                "samples": repeats,
                "nodes": nodes,
                "best_elapsed": times["best"],
                "median_elapsed": times["median"],
                "mean_elapsed": times["mean"],
                "best_nps": nodes / times["best"] if times["best"] else 0.0,
                "median_nps": nodes / times["median"] if times["median"] else 0.0,
                "peak_memory_bytes": max(memory_samples) if memory_samples else 0,
            }
        )
    return records


def run_search_benchmarks(positions: Iterable[BenchmarkPosition], repeats: int) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for bench in positions:
        elapsed_samples: list[float] = []
        memory_samples: list[int] = []
        last_nodes = 0
        last_best = ""
        for sample in range(repeats):
            position = Position.from_fen(bench.fen)
            engine = SearchEngine()
            config = SearchConfig(max_depth=bench.search_depth, time_limit=None)
            result, elapsed, peak = _timed_with_memory(lambda: engine.search(position, config))
            elapsed_samples.append(elapsed)
            memory_samples.append(peak)
            last_nodes = result.nodes
            last_best = result.best_move.uci() if result.best_move else "0000"
            row: dict[str, object] = {
                "kind": "search_sample",
                "position": bench.name,
                "depth": bench.search_depth,
                "sample": sample,
                "best_move": last_best,
                "score": result.score,
                "nodes": result.nodes,
                "elapsed": elapsed,
                "nps": result.nodes / elapsed if elapsed else 0.0,
                "pv": " ".join(move.uci() for move in result.principal_variation),
                "peak_memory_bytes": peak,
            }
            row.update({f"stats_{key}": value for key, value in result.stats.to_dict().items()})
            records.append(row)
            for depth_report in result.depth_reports:
                report = depth_report.to_dict()
                records.append(
                    {
                        "kind": "search_depth",
                        "position": bench.name,
                        "sample": sample,
                        "depth": report["depth"],
                        "score": report["score"],
                        "best_move": report["best_move"],
                        "nodes": report["nodes"],
                        "elapsed": report["elapsed"],
                        "pv": " ".join(report["principal_variation"]),
                    }
                )
        times = _summary(elapsed_samples)
        records.append(
            {
                "kind": "search_summary",
                "position": bench.name,
                "depth": bench.search_depth,
                "samples": repeats,
                "best_move": last_best,
                "nodes": last_nodes,
                "best_elapsed": times["best"],
                "median_elapsed": times["median"],
                "mean_elapsed": times["mean"],
                "best_nps": last_nodes / times["best"] if times["best"] else 0.0,
                "median_nps": last_nodes / times["median"] if times["median"] else 0.0,
                "peak_memory_bytes": max(memory_samples) if memory_samples else 0,
            }
        )
    return records


def run_evaluation_benchmarks(positions: Iterable[BenchmarkPosition], repeats: int, iterations: int) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for bench in positions:
        position = Position.from_fen(bench.fen)
        elapsed_samples: list[float] = []
        score = 0
        for sample in range(repeats):
            def run_loop() -> int:
                total = 0
                for _ in range(iterations):
                    total += evaluate(position)
                return total

            total, elapsed, peak = _timed_with_memory(run_loop)
            score = total // iterations
            elapsed_samples.append(elapsed)
            records.append(
                {
                    "kind": "evaluation_sample",
                    "position": bench.name,
                    "sample": sample,
                    "iterations": iterations,
                    "score": score,
                    "elapsed": elapsed,
                    "evals_per_second": iterations / elapsed if elapsed else 0.0,
                    "peak_memory_bytes": peak,
                }
            )
        times = _summary(elapsed_samples)
        records.append(
            {
                "kind": "evaluation_summary",
                "position": bench.name,
                "samples": repeats,
                "iterations": iterations,
                "score": score,
                "best_elapsed": times["best"],
                "median_elapsed": times["median"],
                "mean_elapsed": times["mean"],
                "best_evals_per_second": iterations / times["best"] if times["best"] else 0.0,
            }
        )
    return records


def play_engine_match(
    *,
    depth_a: int,
    depth_b: int,
    max_plies: int,
    start_fen: str,
) -> dict[str, object]:
    position = Position.from_fen(start_fen)
    engines = {1: SearchEngine(), -1: SearchEngine()}
    depths = {1: depth_a, -1: depth_b}
    moves: list[str] = []
    scores: list[int] = []
    for _ply in range(max_plies):
        status = position.status()
        if status.is_terminal:
            break
        result = engines[position.turn].search(
            position,
            SearchConfig(max_depth=depths[position.turn], time_limit=None),
        )
        if result.best_move is None:
            break
        moves.append(result.best_move.uci())
        scores.append(result.score)
        position = position.make_move(result.best_move)
    status = position.status()
    return {
        "kind": "engine_match",
        "depth_a_white": depth_a,
        "depth_b_black": depth_b,
        "max_plies": max_plies,
        "plies": len(moves),
        "moves": " ".join(moves),
        "scores": " ".join(str(score) for score in scores),
        "final_fen": position.to_fen(),
        "final_state": status.state,
        "final_reason": status.reason,
    }


def write_json(records: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(records: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for record in records for key in record})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic ChessForge benchmarks.")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--eval-iterations", type=int, default=100)
    parser.add_argument("--json", type=Path, default=Path("benchmarks/results.json"))
    parser.add_argument("--csv", type=Path, default=Path("benchmarks/results.csv"))
    parser.add_argument("--skip-match", action="store_true")
    parser.add_argument("--match-plies", type=int, default=24)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")
    records: list[dict[str, object]] = []
    records.extend(run_perft_benchmarks(BENCHMARK_SUITE, args.repeats))
    records.extend(run_search_benchmarks(BENCHMARK_SUITE, args.repeats))
    records.extend(run_evaluation_benchmarks(BENCHMARK_SUITE, args.repeats, args.eval_iterations))
    if not args.skip_match:
        records.append(
            play_engine_match(
                depth_a=2,
                depth_b=2,
                max_plies=args.match_plies,
                start_fen=BENCHMARK_SUITE[0].fen,
            )
        )
    write_json(records, args.json)
    write_csv(records, args.csv)
    print(f"wrote {len(records)} records to {args.json} and {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

