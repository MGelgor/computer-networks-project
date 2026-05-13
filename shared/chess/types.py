from dataclasses import dataclass
from enum import Enum
from typing import Optional

BOARD_SIZE = 8
PROMOTION_CHOICES = ("queen", "rook", "bishop", "knight")


class Color(str, Enum):
    WHITE = "white"
    BLACK = "black"

    @property
    def opposite(self) -> "Color":
        return Color.BLACK if self is Color.WHITE else Color.WHITE


class PieceType(str, Enum):
    KING = "king"
    QUEEN = "queen"
    ROOK = "rook"
    BISHOP = "bishop"
    KNIGHT = "knight"
    PAWN = "pawn"

    @property
    def uci_letter(self) -> str:
        return {
            PieceType.QUEEN: "q",
            PieceType.ROOK: "r",
            PieceType.BISHOP: "b",
            PieceType.KNIGHT: "n",
        }[self]

    @classmethod
    def from_uci_letter(cls, letter: str) -> "PieceType":
        normalized = letter.lower()
        mapping = {
            "q": cls.QUEEN,
            "r": cls.ROOK,
            "b": cls.BISHOP,
            "n": cls.KNIGHT,
        }
        if normalized not in mapping:
            raise ValueError(f"Unsupported promotion letter: {letter!r}")
        return mapping[normalized]


class GameResult(str, Enum):
    ONGOING = "ongoing"
    WHITE_WIN = "1-0"
    BLACK_WIN = "0-1"
    DRAW = "1/2-1/2"


@dataclass(frozen=True)
class Square:
    file: int
    rank: int

    @classmethod
    def from_algebraic(cls, text: str) -> "Square":
        if len(text) != 2:
            raise ValueError(f"Invalid square notation: {text!r}")
        file_char, rank_char = text[0].lower(), text[1]
        if file_char < "a" or file_char > "h":
            raise ValueError(f"Invalid file in square notation: {text!r}")
        if rank_char < "1" or rank_char > "8":
            raise ValueError(f"Invalid rank in square notation: {text!r}")
        return cls(file=ord(file_char) - ord("a"), rank=int(rank_char) - 1)

    def to_algebraic(self) -> str:
        return f"{chr(self.file + ord('a'))}{self.rank + 1}"

    def offset(self, file_delta: int, rank_delta: int) -> Optional["Square"]:
        file = self.file + file_delta
        rank = self.rank + rank_delta
        if 0 <= file < BOARD_SIZE and 0 <= rank < BOARD_SIZE:
            return Square(file=file, rank=rank)
        return None

    def __str__(self) -> str:
        return self.to_algebraic()


@dataclass(frozen=True)
class Piece:
    color: Color
    piece_type: PieceType

    def symbol(self) -> str:
        symbols = {
            PieceType.KING: "k",
            PieceType.QUEEN: "q",
            PieceType.ROOK: "r",
            PieceType.BISHOP: "b",
            PieceType.KNIGHT: "n",
            PieceType.PAWN: "p",
        }
        text = symbols[self.piece_type]
        return text.upper() if self.color is Color.WHITE else text


@dataclass
class CastlingRights:
    white_kingside: bool = False
    white_queenside: bool = False
    black_kingside: bool = False
    black_queenside: bool = False

    def copy(self) -> "CastlingRights":
        return CastlingRights(
            white_kingside=self.white_kingside,
            white_queenside=self.white_queenside,
            black_kingside=self.black_kingside,
            black_queenside=self.black_queenside,
        )


@dataclass(frozen=True)
class Move:
    from_square: Square
    to_square: Square
    promotion: Optional[PieceType] = None
    is_kingside_castle: bool = False
    is_queenside_castle: bool = False
    is_en_passant: bool = False

    def to_uci(self) -> str:
        text = f"{self.from_square.to_algebraic()}{self.to_square.to_algebraic()}"
        if self.promotion is not None:
            text += self.promotion.uci_letter
        return text

    @classmethod
    def from_uci(cls, text: str) -> "Move":
        if len(text) not in (4, 5):
            raise ValueError(f"Invalid UCI move: {text!r}")
        from_square = Square.from_algebraic(text[0:2])
        to_square = Square.from_algebraic(text[2:4])
        promotion = PieceType.from_uci_letter(text[4]) if len(text) == 5 else None
        return cls(from_square=from_square, to_square=to_square, promotion=promotion)

    def __str__(self) -> str:
        return self.to_uci()


