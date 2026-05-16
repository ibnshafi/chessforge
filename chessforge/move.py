"""Move representation and UCI conversion."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import PROMOTION_CHARS, PROMOTION_PIECES, square_name

PROMOTION_TO_CHAR = {value: key for key, value in PROMOTION_CHARS.items()}


@dataclass(frozen=True, slots=True)
class Move:
    """A compact chess move.

    Special move flags are stored explicitly so the board transition does not
    need to infer en passant or castling after the fact.
    """

    from_sq: int
    to_sq: int
    promotion: int = 0
    is_en_passant: bool = False
    is_castling: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.from_sq < 64:
            raise ValueError(f"from_sq out of range: {self.from_sq}")
        if not 0 <= self.to_sq < 64:
            raise ValueError(f"to_sq out of range: {self.to_sq}")
        if self.promotion and self.promotion not in PROMOTION_PIECES:
            raise ValueError(f"Invalid promotion piece: {self.promotion}")

    def uci(self) -> str:
        text = square_name(self.from_sq) + square_name(self.to_sq)
        if self.promotion:
            text += PROMOTION_TO_CHAR[self.promotion]
        return text

    def __str__(self) -> str:
        return self.uci()
