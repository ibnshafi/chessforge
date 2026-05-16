import tempfile
import unittest
from pathlib import Path

from chessforge.core import Position
from chessforge.ml import (
    FEATURE_DIM,
    LinearNnueEvaluator,
    TrainingExample,
    compare_evaluators,
    export_csv,
    export_jsonl,
    extract_sparse_features,
    generate_self_play_dataset,
    train_linear_evaluator,
)
from chessforge.search import SearchConfig, SearchEngine


class MlTests(unittest.TestCase):
    def test_feature_extraction_is_sparse_and_bounded(self) -> None:
        features = extract_sparse_features(Position.starting())
        self.assertEqual(features, tuple(sorted(features)))
        self.assertTrue(all(0 <= feature < FEATURE_DIM for feature in features))
        self.assertGreater(len(features), 32)

    def test_linear_evaluator_can_drive_search(self) -> None:
        evaluator = LinearNnueEvaluator.zero()
        result = SearchEngine(evaluator=evaluator.evaluate).search(
            Position.starting(),
            SearchConfig(max_depth=1, time_limit=None),
        )
        self.assertIsNotNone(result.best_move)

    def test_training_and_exports(self) -> None:
        example = TrainingExample(Position.starting().to_fen(), 25, 0, 0)
        evaluator = train_linear_evaluator([example], epochs=1, learning_rate=0.001)
        rows = compare_evaluators(evaluator, [Position.starting()])
        self.assertEqual(len(rows), 1)
        with tempfile.TemporaryDirectory() as temp_dir:
            jsonl = Path(temp_dir) / "data.jsonl"
            csv_path = Path(temp_dir) / "data.csv"
            export_jsonl([example], jsonl)
            export_csv([example], csv_path)
            self.assertIn("target", jsonl.read_text(encoding="utf-8"))
            self.assertIn("fen,target,ply,game", csv_path.read_text(encoding="utf-8").splitlines()[0])

    def test_self_play_dataset_generation_is_deterministic(self) -> None:
        kwargs = {
            "games": 1,
            "depth": 1,
            "max_plies": 2,
            "start_fen": Position.starting().to_fen(),
        }
        self.assertEqual(generate_self_play_dataset(**kwargs), generate_self_play_dataset(**kwargs))


if __name__ == "__main__":
    unittest.main()

