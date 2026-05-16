# Search System

ChessForge uses iterative-deepening negamax alpha-beta. Scores are interpreted from the side to move inside the recursion and converted from white-positive static evaluation by multiplying with the side sign.

The search stack now includes:

- Principal Variation Search: after the first ordered move, later moves are searched with a null window. If a move proves better than alpha, it is re-searched with the full window. Good move ordering makes most non-PV moves fail low quickly.
- Aspiration windows: depths after the early iterations search around the previous score. A fail-low or fail-high triggers a full-window re-search. This reduces search work when evaluation is stable between depths.
- Transposition table bounds: entries store exact, lower-bound, and upper-bound scores with depth and generation metadata. Replacement prefers current-generation and deeper entries.
- Null-move pruning: quiet non-check nodes with non-pawn material allow a reduced-depth pass move. A fail-high indicates the side can likely preserve beta even after doing nothing, so the branch is pruned. The implementation disables null move in check and in low-material pawn-only cases to reduce zugzwang risk.
- Late Move Reductions: late quiet moves in non-check nodes are searched at reduced depth. If the reduced search exceeds alpha, the move is re-searched normally.
- Check extensions: checking moves receive one extra ply because tactical forcing lines are unstable at fixed depth.
- Killer heuristic: quiet beta-cutoff moves are stored by ply and ordered highly when they recur at the same depth.
- History heuristic: quiet beta-cutoff moves accumulate depth-squared bonuses keyed by piece/from/to.
- SEE-assisted ordering: captures receive a static exchange estimate so losing captures are not blindly treated like winning tactics.
- Mate-distance pruning: alpha and beta are tightened by ply-relative mate bounds so the engine prefers faster mates and avoids impossible mate scores.
- Internal iterative deepening: deep nodes without a TT move perform a shallow probe to seed move ordering.

The instrumentation schema records nodes, qnodes, max ply, TT probe/hit/cutoff rates, beta cutoffs, PVS searches and re-searches, null-move searches/prunes, LMR reductions, check extensions, killer/history hits, SEE evaluations, branching-factor estimates, and depth reports.

Correctness constraints:

- All root moves still come from `Position.legal_moves`.
- Search-selective rules never create moves; they only reduce or reorder legal branches.
- Null-move pruning is disabled while in check.
- Quiescence uses legal captures and promotions.
- Public results remain deterministic because move ordering uses fixed scores and UCI tie-breaks.

