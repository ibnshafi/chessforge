import json
import tempfile
import unittest
from pathlib import Path

from chessforge.benchmark import (
    BENCHMARK_SUITE,
    play_engine_match,
    run_evaluation_benchmarks,
    run_perft_benchmarks,
    run_search_benchmarks,
    write_csv,
    write_json,
)


class BenchmarkTests(unittest.TestCase):
    def test_perft_search_and_evaluation_records_have_required_fields(self) -> None:
        suite = BENCHMARK_SUITE[:1]
        perft_records = run_perft_benchmarks(suite, repeats=1)
        search_records = run_search_benchmarks(suite, repeats=1)
        eval_records = run_evaluation_benchmarks(suite, repeats=1, iterations=2)

        self.assertTrue(any(record["kind"] == "perft_summary" for record in perft_records))
        search_sample = next(record for record in search_records if record["kind"] == "search_sample")
        self.assertGreater(search_sample["nodes"], 0)
        self.assertIn("stats_tt_probes", search_sample)
        self.assertIn("stats_average_ordered_branching_factor", search_sample)
        eval_sample = next(record for record in eval_records if record["kind"] == "evaluation_sample")
        self.assertIn("evals_per_second", eval_sample)

    def test_engine_match_is_deterministic_for_fixed_depths(self) -> None:
        kwargs = {
            "depth_a": 1,
            "depth_b": 1,
            "max_plies": 6,
            "start_fen": BENCHMARK_SUITE[0].fen,
        }
        self.assertEqual(play_engine_match(**kwargs), play_engine_match(**kwargs))

    def test_json_and_csv_exports_are_written(self) -> None:
        records = [{"kind": "unit", "position": "x", "nodes": 1}]
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "records.json"
            csv_path = Path(temp_dir) / "records.csv"
            write_json(records, json_path)
            write_csv(records, csv_path)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), records)
            self.assertIn("kind,nodes,position", csv_path.read_text(encoding="utf-8").splitlines()[0])


if __name__ == "__main__":
    unittest.main()

