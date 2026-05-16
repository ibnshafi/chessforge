# Evaluation System

The evaluator returns a centipawn score from White's perspective. Positive means White is better; negative means Black is better.

Implemented terms:

- Incremental material balance from `Position.material_balance`.
- Piece-square tables for pawns, knights, bishops, rooks, queens, and king placement.
- Tapered king PST interpolation between middlegame safety and endgame activity.
- Bishop pair bonus.
- Pseudo-legal mobility differential.
- Pawn shield around both kings.
- King attack pressure around both kings.
- Pawn structure: doubled pawns, isolated pawns, backward pawns, passed pawns, and connected passed pawns.
- Rook file activity: open files, semi-open files, and seventh-rank rooks.
- Outposts for protected knights and bishops that cannot be challenged by enemy pawns.
- King tropism for attacking pieces near the enemy king.
- Space control in central files on advanced ranks.
- Threat scoring for attacked enemy non-king pieces.
- Tempo bonus for the side to move.
- Opposition scoring in king-heavy endings.
- Fortress scaling in sparse low-material positions.

The evaluation is intentionally deterministic and integer-valued. It is not tuned by self-play yet, but every term has explicit chess meaning and bounded centipawn scale. This makes ablation experiments possible: search can compare configurations while the benchmark runner records node count, score, PV, and speed.

Computationally expensive terms are mobility, space, king pressure, and threats because they call move or attack generation. The benchmark suite therefore includes evaluation throughput records. That measurement makes evaluation complexity visible instead of hiding it inside search time.

