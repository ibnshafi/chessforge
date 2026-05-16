"""Deterministic ML and NNUE-style experimentation utilities."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .constants import BLACK, KING, WHITE, color_of, piece_type
from .core import Position
from .evaluation import evaluate
from .search import SearchConfig, SearchEngine

PIECE_SQUARE_FEATURES = 12 * 64
SIDE_TO_MOVE_FEATURE = PIECE_SQUARE_FEATURES
CASTLING_BASE_FEATURE = SIDE_TO_MOVE_FEATURE + 1
FEATURE_DIM = CASTLING_BASE_FEATURE + 16


@dataclass(frozen=True, slots=True)
class TrainingExample:
    fen: str
    target: int
    ply: int
    game: int

    def to_dict(self) -> dict[str, int | str]:
        return {"fen": self.fen, "target": self.target, "ply": self.ply, "game": self.game}


@dataclass(frozen=True, slots=True)
class LinearNnueEvaluator:
    """Quantized sparse linear evaluator over piece-square features."""

    weights: tuple[int, ...]
    bias: int = 0
    scale: int = 1

    @classmethod
    def zero(cls) -> "LinearNnueEvaluator":
        return cls(weights=(0,) * FEATURE_DIM)

    def evaluate(self, position: Position) -> int:
        total = self.bias
        for feature in extract_sparse_features(position):
            total += self.weights[feature]
        return round(total / self.scale)


def feature_index(piece: int, square_index: int) -> int:
    color_offset = 0 if color_of(piece) == WHITE else 6
    return (color_offset + piece_type(piece) - 1) * 64 + square_index


def extract_sparse_features(position: Position) -> tuple[int, ...]:
    features: list[int] = []
    for sq, piece in enumerate(position.board):
        if piece:
            features.append(feature_index(piece, sq))
    if position.turn == BLACK:
        features.append(SIDE_TO_MOVE_FEATURE)
    features.append(CASTLING_BASE_FEATURE + position.castling)
    return tuple(sorted(features))


def generate_self_play_dataset(
    *,
    games: int,
    depth: int,
    max_plies: int,
    start_fen: str,
) -> list[TrainingExample]:
    examples: list[TrainingExample] = []
    for game_index in range(games):
        position = Position.from_fen(start_fen)
        engine = SearchEngine()
        for ply in range(max_plies):
            status = position.status()
            if status.is_terminal:
                break
            result = engine.search(position, SearchConfig(max_depth=depth, time_limit=None))
            target = result.score if position.turn == WHITE else -result.score
            examples.append(TrainingExample(position.to_fen(), target, ply, game_index))
            if result.best_move is None:
                break
            position = position.make_move(result.best_move)
    return examples


def export_jsonl(examples: list[TrainingExample], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example.to_dict(), sort_keys=True) + "\n")


def export_csv(examples: list[TrainingExample], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["fen", "target", "ply", "game"])
        writer.writeheader()
        for example in examples:
            writer.writerow(example.to_dict())


def train_linear_evaluator(
    examples: list[TrainingExample],
    *,
    epochs: int = 4,
    learning_rate: float = 0.01,
    l2: float = 0.0001,
    quantization: int = 16,
) -> LinearNnueEvaluator:
    weights = [0.0] * FEATURE_DIM
    bias = 0.0
    if not examples:
        return LinearNnueEvaluator.zero()
    for _epoch in range(max(1, epochs)):
        for example in examples:
            position = Position.from_fen(example.fen)
            features = extract_sparse_features(position)
            prediction = bias + sum(weights[index] for index in features)
            error = max(-2000.0, min(2000.0, prediction - example.target))
            step = learning_rate * error
            bias -= step
            for index in features:
                weights[index] -= step + learning_rate * l2 * weights[index]
    quantized = tuple(round(value * quantization) for value in weights)
    return LinearNnueEvaluator(weights=quantized, bias=round(bias * quantization), scale=quantization)


def compare_evaluators(evaluator: LinearNnueEvaluator, positions: list[Position]) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for position in positions:
        classical = evaluate(position)
        neural = evaluator.evaluate(position)
        rows.append(
            {
                "fen": position.to_fen(),
                "classical": classical,
                "neural": neural,
                "delta": neural - classical,
            }
        )
    return rows

