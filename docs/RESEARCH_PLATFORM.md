# Research Platform

ChessForge now includes first-class experiment tooling:

- `chessforge-bench` runs perft, search, evaluation, and deterministic engine-match benchmarks.
- Benchmark records export to JSON and CSV.
- Search records include instrumentation counters, PVs, depth reports, node rates, and memory peaks.
- `chessforge-research` runs deterministic search-heuristic ablations and parameter sweeps.
- `experiments.py` provides round-robin tournaments, score-rate calculation, Elo conversion, and SPRT log-likelihood math.
- `ml.py` provides sparse feature extraction, self-play dataset generation, JSONL/CSV export, quantized linear NNUE-style inference, simple SGD training, and evaluator comparison.
- `visualization.py` exposes attack maps, evaluation heatmaps, PV reports, and move-ordering snapshots.
- `tests/test_fuzz.py` provides seeded playout fuzzing for FEN, Zobrist, king-square, and legal-move invariants.

The project is built around reproducibility:

- Fixed benchmark suites.
- Fixed Zobrist seed.
- Deterministic move ordering.
- Deterministic self-play for fixed depth/configuration.
- No random search decisions.
- Seeded fuzz tests.
- Machine-readable experiment artifacts.

The current benchmark artifacts are:

- `benchmarks/baseline.json` and `benchmarks/baseline.csv`
- `benchmarks/post_evolution.json` and `benchmarks/post_evolution.csv`

These files record the measured consequences of the engine revision. They show that stronger evaluation and selective search change the speed profile: node counts can fall while per-node cost rises. That is an honest engine-engineering result and gives the project a concrete optimization target for later make/unmake and bitboard integration work.

