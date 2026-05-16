"""Instrumentation data models for search and benchmark reporting.

The engine keeps measurement structures deliberately separate from the
algorithmic code.  Search updates a mutable ``SearchStats`` instance on hot
paths, while benchmark tooling serializes the counters through ``to_dict``.
This gives ChessForge a stable observability layer without forcing search
callers to parse logs or depend on private engine fields.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class SearchStats:
    """Mutable counters collected during a single search call.

    The fields include counters for features that are already implemented and
    reserved counters for near-term search upgrades.  Keeping those fields in
    the schema from the start makes benchmark output comparable as the engine
    evolves from plain alpha-beta toward PVS, null-move pruning, LMR, and
    killer/history move ordering.
    """

    nodes: int = 0
    qnodes: int = 0
    max_ply: int = 0
    max_q_depth: int = 0
    depth_iterations: int = 0
    timeout_checks: int = 0

    tt_probes: int = 0
    tt_hits: int = 0
    tt_usable_hits: int = 0
    tt_cutoffs: int = 0
    tt_stores: int = 0
    tt_exact_stores: int = 0
    tt_lower_stores: int = 0
    tt_upper_stores: int = 0

    beta_cutoffs: int = 0
    q_beta_cutoffs: int = 0
    stand_pat_cutoffs: int = 0

    move_order_batches: int = 0
    move_order_moves: int = 0
    tt_move_order_hits: int = 0
    checking_moves_ordered: int = 0
    tactical_moves_ordered: int = 0

    legal_move_batches: int = 0
    legal_moves_total: int = 0

    aspiration_researches: int = 0
    pvs_searches: int = 0
    pvs_researches: int = 0
    null_move_prunes: int = 0
    null_move_searches: int = 0
    lmr_reductions: int = 0
    iid_searches: int = 0
    check_extensions: int = 0
    killer_move_hits: int = 0
    history_move_hits: int = 0
    see_evaluations: int = 0
    mate_distance_prunes: int = 0

    def record_legal_batch(self, move_count: int) -> None:
        self.legal_move_batches += 1
        self.legal_moves_total += move_count

    def record_tt_store(self, flag: int) -> None:
        self.tt_stores += 1
        if flag == 0:
            self.tt_exact_stores += 1
        elif flag == 1:
            self.tt_lower_stores += 1
        elif flag == 2:
            self.tt_upper_stores += 1

    @property
    def non_quiescence_nodes(self) -> int:
        return self.nodes - self.qnodes

    @property
    def tt_hit_rate(self) -> float:
        return self.tt_hits / self.tt_probes if self.tt_probes else 0.0

    @property
    def tt_usable_hit_rate(self) -> float:
        return self.tt_usable_hits / self.tt_probes if self.tt_probes else 0.0

    @property
    def beta_cutoff_rate(self) -> float:
        return self.beta_cutoffs / self.non_quiescence_nodes if self.non_quiescence_nodes else 0.0

    @property
    def average_ordered_branching_factor(self) -> float:
        return self.move_order_moves / self.move_order_batches if self.move_order_batches else 0.0

    @property
    def average_legal_branching_factor(self) -> float:
        return self.legal_moves_total / self.legal_move_batches if self.legal_move_batches else 0.0

    def to_dict(self) -> dict[str, int | float]:
        data: dict[str, int | float] = asdict(self)
        data["non_quiescence_nodes"] = self.non_quiescence_nodes
        data["tt_hit_rate"] = self.tt_hit_rate
        data["tt_usable_hit_rate"] = self.tt_usable_hit_rate
        data["beta_cutoff_rate"] = self.beta_cutoff_rate
        data["average_ordered_branching_factor"] = self.average_ordered_branching_factor
        data["average_legal_branching_factor"] = self.average_legal_branching_factor
        return data


@dataclass(frozen=True, slots=True)
class DepthReport:
    """Per-iteration iterative-deepening report."""

    depth: int
    score: int
    best_move: str | None
    nodes: int
    elapsed: float
    principal_variation: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "depth": self.depth,
            "score": self.score,
            "best_move": self.best_move,
            "nodes": self.nodes,
            "elapsed": self.elapsed,
            "principal_variation": list(self.principal_variation),
        }
