# ChessForge

ChessForge is a dependency-free chess system implemented from scratch in Python:

- complete FIDE move legality, including castling, en passant, promotion, checkmate, stalemate, repetition, and the 50-move rule
- immutable game-state transitions with Zobrist repetition keys
- legal move generation with attack detection and king-safety filtering
- perft and divide tooling for move-generator validation
- modern deterministic search with PVS, aspiration windows, transposition table bounds, null-move pruning, late move reductions, check extensions, killer/history heuristics, quiescence search, SEE-assisted ordering, and detailed instrumentation
- advanced deterministic evaluation with pawn structure, passed pawns, rook files, outposts, king tropism, space, threats, tempo, opposition, and fortress scaling
- benchmark, research, ML, and visualization tooling for reproducible engine experiments
- playable CLI modes for human vs human, human vs AI, and AI vs AI
- minimal UCI loop for chess GUI integration

No external chess engines or chess libraries are used.

## File Structure

```text
chessforge/
  constants.py     board constants, piece codes, square helpers
  attacks.py       precomputed pawn, knight, and king attack geometry
  bitboards.py     derived bitboard views and attack masks
  move.py          compact move object and UCI formatting
  core.py          FEN, rules, legal moves, state transitions, status, perft
  evaluation.py    advanced deterministic positional evaluation
  search.py        PVS alpha-beta, quiescence, pruning, TT, instrumentation
  metrics.py       search counters and depth reports
  benchmark.py     reproducible perft/search/eval benchmark exports
  experiments.py   tournaments, ablations, Elo, SPRT, parameter sweeps
  ml.py            self-play data, sparse features, quantized evaluator
  visualization.py attack maps, PV reports, evaluation heatmaps
  cli.py           playable command-line app
  uci.py           UCI protocol entrypoint
docs/
  ARCHITECTURE.md
  SEARCH.md
  EVALUATION.md
  RESEARCH_PLATFORM.md
examples/
  ai_vs_ai.py
  sample_ai_vs_ai.txt
tests/
  test_perft.py
  test_rules.py
  test_search.py
```

## Run

Use Python 3.10 or newer.

```bash
python -m chessforge.cli --mode human-ai --human-color white --depth 3 --time 2
python -m chessforge.cli --mode human-human
python -m chessforge.cli --mode ai-ai --depth 2 --time 1 --max-plies 80
python -m chessforge.benchmark --repeats 1 --eval-iterations 20
python -m chessforge.research --depths 1,2 --max-plies 8
```

Standalone example:

```bash
python examples/ai_vs_ai.py --depth 2 --time 0.5 --max-plies 40
```

UCI:

```bash
python -m chessforge.uci
```

Then send commands such as:

```text
uci
isready
position startpos moves e2e4 e7e5
go depth 4
quit
```

## CLI Commands

Inside the playable CLI:

```text
e2e4        play a UCI move; promotions use e7e8q/e7e8n
legal       list legal moves
fen         print current FEN
board       print board
eval        print static evaluation
perft N     run perft at depth N
divide N    run perft divide at depth N
undo        undo one ply
quit        exit
```

## Test

```bash
python -m unittest discover -s tests -v
```

The suite validates:

- starting position perft: `20, 400, 8902`
- Kiwipete perft: `48, 2039, 97862`
- en-passant/endgame perft: `14, 191, 2812`
- castling edge cases
- en passant discovered-check illegality
- promotion choices
- checkmate and stalemate detection
- threefold repetition
- 50-move rule
- search returning legal moves only

## Architecture Notes

The board is a 64-square array indexed `a1 == 0` through `h8 == 63`. Pieces are signed integers: positive for White, negative for Black, with the magnitude as the piece type.

`Position` is immutable from the public API. Moves create new positions, while the engine uses a trusted transient constructor internally for high-volume legality filtering. Full game moves compute Zobrist hashes and preserve repetition history.

Move generation first creates pseudo-legal moves and then applies each candidate to ensure the moving side's king is not left in check. This catches pinned pieces, en passant discovered checks, king moves into attack, and all castling path attacks.

Fixed pawn, knight, and king attack geometry lives in `attacks.py`. These tables are pure coordinate data, so they are deterministic and reusable across legality, move generation, evaluation, and bitboard work. Legal move filtering applies each pseudo-legal move to a transient board copy and calls the shared attack detector directly; full immutable `Position` objects are still created for real state transitions, but not for short-lived attack probes. This preserves the clean public model while reducing hot-path allocation.

The evaluator combines cached material with PST matrices, mobility, bishop-pair bonuses, pawn structure, rook activity, outposts, king safety, threats, space, tempo, endgame opposition, and fortress scaling. The search is instrumented negamax alpha-beta with iterative deepening, PVS, aspiration windows, quiescence search, selective pruning, deterministic move ordering, and a transposition table keyed by deterministic Zobrist hashes.
