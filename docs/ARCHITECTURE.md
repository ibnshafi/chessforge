# ChessForge Architecture

ChessForge is organized as a deterministic layered engine:

1. `constants.py` defines square math, signed piece encoding, castling bits, movement vectors, and material values.
2. `attacks.py` precomputes fixed pawn, knight, and king attack geometry.
3. `core.py` owns canonical chess state, FEN, legality, move generation, hashing, draw logic, and perft.
4. `bitboards.py` derives immutable bitboard views from mailbox state for attack masks, visualization, ML features, and representation migration.
5. `evaluation.py` scores positions with material, PSTs, tapered king placement, pawn structure, rook files, outposts, threats, space, king pressure, tempo, opposition, and fortress scaling.
6. `search.py` owns iterative deepening, alpha-beta, PVS, aspiration windows, null-move pruning, LMR, check extensions, killer/history heuristics, SEE-assisted ordering, TT bounds, and instrumentation.
7. `benchmark.py`, `experiments.py`, `ml.py`, and `visualization.py` turn the engine into a measurable research platform.

The canonical board remains a 64-square mailbox tuple because it is inspectable and already perft-validated. High-performance representations are introduced as derived views, not replacements, so bitboard experiments cannot corrupt legal move generation. This hybrid model creates a safe migration channel: correctness remains anchored in mailbox rules while performance-oriented tools can consume bitboards.

`Position` is immutable from the public API. It stores board, turn, castling, en-passant, clocks, Zobrist hash, repetition history, cached king squares, and material balance. The cached king squares eliminate repeated `board.index()` scans in check detection. The material balance gives evaluation an incremental material base. Private trusted construction preserves speed in search/perft while public constructors validate invariants.

Search accepts an injected evaluator. The default is the classical handcrafted evaluator; `ml.LinearNnueEvaluator.evaluate` can also drive search. This interface separates tree search from value approximation and makes evaluation experiments measurable without changing alpha-beta code.

