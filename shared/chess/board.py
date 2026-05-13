from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from .types import (
    BOARD_SIZE,
    CastlingRights,
    Color,
    GameResult,
    Move,
    Piece,
    PieceType,
    PROMOTION_CHOICES,
    Square,
)

WHITE_BACK_RANK = (
    PieceType.ROOK,
    PieceType.KNIGHT,
    PieceType.BISHOP,
    PieceType.QUEEN,
    PieceType.KING,
    PieceType.BISHOP,
    PieceType.KNIGHT,
    PieceType.ROOK,
)

KING_SIDE_KING_FROM = Square.from_algebraic("e1")
QUEEN_SIDE_KING_FROM = Square.from_algebraic("e8")
WHITE_KING_FROM = Square.from_algebraic("e1")
BLACK_KING_FROM = Square.from_algebraic("e8")
WHITE_KING_ROOK = Square.from_algebraic("h1")
WHITE_QUEEN_ROOK = Square.from_algebraic("a1")
BLACK_KING_ROOK = Square.from_algebraic("h8")
BLACK_QUEEN_ROOK = Square.from_algebraic("a8")

KNIGHT_OFFSETS = (
    (1, 2),
    (2, 1),
    (2, -1),
    (1, -2),
    (-1, -2),
    (-2, -1),
    (-2, 1),
    (-1, 2),
)

KING_OFFSETS = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)

SLIDING_DIRECTIONS = {
    PieceType.ROOK: ((1, 0), (-1, 0), (0, 1), (0, -1)),
    PieceType.BISHOP: ((1, 1), (1, -1), (-1, 1), (-1, -1)),
    PieceType.QUEEN: ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)),
}


@dataclass
class Board:
    squares: List[Optional[Piece]] = field(default_factory=lambda: [None] * (BOARD_SIZE * BOARD_SIZE))
    side_to_move: Color = Color.WHITE
    castling_rights: CastlingRights = field(default_factory=CastlingRights)
    en_passant_target: Optional[Square] = None
    move_history: List[Move] = field(default_factory=list)
    game_result: GameResult = GameResult.ONGOING

    def __post_init__(self) -> None:
        if len(self.squares) != BOARD_SIZE * BOARD_SIZE:
            raise ValueError("Board must contain exactly 64 squares")

    @classmethod
    def empty(
        cls,
        side_to_move: Color = Color.WHITE,
        castling_rights: Optional[CastlingRights] = None,
        en_passant_target: Optional[Square] = None,
    ) -> "Board":
        return cls(
            squares=[None] * (BOARD_SIZE * BOARD_SIZE),
            side_to_move=side_to_move,
            castling_rights=castling_rights.copy() if castling_rights else CastlingRights(),
            en_passant_target=en_passant_target,
        )

    @classmethod
    def from_piece_map(
        cls,
        pieces: Dict[object, Piece],
        side_to_move: Color = Color.WHITE,
        castling_rights: Optional[CastlingRights] = None,
        en_passant_target: Optional[object] = None,
    ) -> "Board":
        board = cls.empty(side_to_move=side_to_move, castling_rights=castling_rights)
        for square_ref, piece in pieces.items():
            square = square_ref if isinstance(square_ref, Square) else Square.from_algebraic(square_ref)
            board.set_piece(square, piece)
        if en_passant_target is not None:
            board.en_passant_target = (
                en_passant_target if isinstance(en_passant_target, Square) else Square.from_algebraic(en_passant_target)
            )
        return board

    @classmethod
    def initial(cls) -> "Board":
        board = cls.empty(
            side_to_move=Color.WHITE,
            castling_rights=CastlingRights(
                white_kingside=True,
                white_queenside=True,
                black_kingside=True,
                black_queenside=True,
            ),
        )
        for file, piece_type in enumerate(WHITE_BACK_RANK):
            board.set_piece(Square(file=file, rank=0), Piece(Color.WHITE, piece_type))
            board.set_piece(Square(file=file, rank=1), Piece(Color.WHITE, PieceType.PAWN))
            board.set_piece(Square(file=file, rank=6), Piece(Color.BLACK, PieceType.PAWN))
            board.set_piece(Square(file=file, rank=7), Piece(Color.BLACK, piece_type))
        return board

    @staticmethod
    def inside(square: Square) -> bool:
        return 0 <= square.file < BOARD_SIZE and 0 <= square.rank < BOARD_SIZE

    @staticmethod
    def index(square: Square) -> int:
        return square.rank * BOARD_SIZE + square.file

    def piece_at(self, square: Square) -> Optional[Piece]:
        return self.squares[self.index(square)]

    def set_piece(self, square: Square, piece: Optional[Piece]) -> None:
        self.squares[self.index(square)] = piece

    def remove_piece(self, square: Square) -> Optional[Piece]:
        index = self.index(square)
        piece = self.squares[index]
        self.squares[index] = None
        return piece

    def copy(self) -> "Board":
        return Board(
            squares=self.squares.copy(),
            side_to_move=self.side_to_move,
            castling_rights=self.castling_rights.copy(),
            en_passant_target=self.en_passant_target,
            move_history=self.move_history.copy(),
            game_result=self.game_result,
        )

    def king_square(self, color: Color) -> Optional[Square]:
        for rank in range(BOARD_SIZE):
            for file in range(BOARD_SIZE):
                square = Square(file=file, rank=rank)
                piece = self.piece_at(square)
                if piece and piece.color is color and piece.piece_type is PieceType.KING:
                    return square
        return None

    def is_square_attacked(self, square: Square, by_color: Color) -> bool:
        pawn_rank_delta = -1 if by_color is Color.WHITE else 1
        for file_delta in (-1, 1):
            attacker_square = square.offset(file_delta, pawn_rank_delta)
            if attacker_square:
                attacker = self.piece_at(attacker_square)
                if attacker and attacker.color is by_color and attacker.piece_type is PieceType.PAWN:
                    return True

        for file_delta, rank_delta in KNIGHT_OFFSETS:
            attacker_square = square.offset(file_delta, rank_delta)
            if attacker_square:
                attacker = self.piece_at(attacker_square)
                if attacker and attacker.color is by_color and attacker.piece_type is PieceType.KNIGHT:
                    return True

        for file_delta, rank_delta in KING_OFFSETS:
            attacker_square = square.offset(file_delta, rank_delta)
            if attacker_square:
                attacker = self.piece_at(attacker_square)
                if attacker and attacker.color is by_color and attacker.piece_type is PieceType.KING:
                    return True

        for piece_type, directions in (
            (PieceType.ROOK, SLIDING_DIRECTIONS[PieceType.ROOK]),
            (PieceType.BISHOP, SLIDING_DIRECTIONS[PieceType.BISHOP]),
            (PieceType.QUEEN, SLIDING_DIRECTIONS[PieceType.QUEEN]),
        ):
            for file_delta, rank_delta in directions:
                current = square
                while True:
                    current = current.offset(file_delta, rank_delta)
                    if current is None:
                        break
                    occupant = self.piece_at(current)
                    if occupant is None:
                        continue
                    if occupant.color is by_color and occupant.piece_type in (
                        piece_type,
                        PieceType.QUEEN if piece_type is not PieceType.QUEEN else PieceType.QUEEN,
                    ):
                        return True
                    break
        return False

    def is_in_check(self, color: Color) -> bool:
        king_square = self.king_square(color)
        if king_square is None:
            return False
        return self.is_square_attacked(king_square, color.opposite)

    def legal_moves(self, color: Optional[Color] = None) -> List[Move]:
        color = self.side_to_move if color is None else color
        moves: list[Move] = []
        for square, piece in self._iter_pieces(color):
            for candidate in self._pseudo_legal_moves_from(square, piece):
                trial = self.copy()
                trial._apply_move_unchecked(candidate)
                if not trial.is_in_check(color):
                    moves.append(candidate)
        return moves

    def is_checkmate(self, color: Optional[Color] = None) -> bool:
        color = self.side_to_move if color is None else color
        return self.is_in_check(color) and not self.legal_moves(color)

    def is_stalemate(self, color: Optional[Color] = None) -> bool:
        color = self.side_to_move if color is None else color
        return not self.is_in_check(color) and not self.legal_moves(color)

    def push(self, move: Move) -> None:
        legal_moves = self.legal_moves(self.side_to_move)
        matched_move = self._match_legal_move(move, legal_moves)
        if matched_move is None:
            raise ValueError(f"Illegal move: {move}")
        move = matched_move
        self._apply_move_unchecked(move)
        self._refresh_game_result()

    def _match_legal_move(self, move: Move, legal_moves: List[Move]) -> Optional[Move]:
        matching_moves = [
            legal_move
            for legal_move in legal_moves
            if legal_move.from_square == move.from_square and legal_move.to_square == move.to_square
        ]
        if not matching_moves:
            return None

        if move.promotion is not None:
            for legal_move in matching_moves:
                if legal_move.promotion == move.promotion:
                    return legal_move
            return None

        for legal_move in matching_moves:
            if legal_move.promotion is None:
                return legal_move

        for legal_move in matching_moves:
            if legal_move.promotion == PieceType.QUEEN:
                return legal_move

        return matching_moves[0]

    def _refresh_game_result(self) -> None:
        if self.legal_moves(self.side_to_move):
            self.game_result = GameResult.ONGOING
            return
        if self.is_in_check(self.side_to_move):
            self.game_result = GameResult.WHITE_WIN if self.side_to_move is Color.BLACK else GameResult.BLACK_WIN
        else:
            self.game_result = GameResult.DRAW

    def _iter_pieces(self, color: Color) -> Iterable[Tuple[Square, Piece]]:
        for rank in range(BOARD_SIZE):
            for file in range(BOARD_SIZE):
                square = Square(file=file, rank=rank)
                piece = self.piece_at(square)
                if piece and piece.color is color:
                    yield square, piece

    def _pseudo_legal_moves_from(self, square: Square, piece: Piece) -> list[Move]:
        if piece.piece_type is PieceType.PAWN:
            return list(self._pawn_moves(square, piece))
        if piece.piece_type is PieceType.KNIGHT:
            return list(self._knight_moves(square, piece))
        if piece.piece_type in (PieceType.ROOK, PieceType.BISHOP, PieceType.QUEEN):
            return list(self._sliding_moves(square, piece))
        if piece.piece_type is PieceType.KING:
            return list(self._king_moves(square, piece))
        return []

    def _pawn_moves(self, square: Square, piece: Piece) -> Iterable[Move]:
        direction = 1 if piece.color is Color.WHITE else -1
        start_rank = 1 if piece.color is Color.WHITE else 6
        promotion_rank = 7 if piece.color is Color.WHITE else 0

        one_step = square.offset(0, direction)
        if one_step and self.piece_at(one_step) is None:
            if one_step.rank == promotion_rank:
                for promotion in self._promotion_pieces():
                    yield Move(square, one_step, promotion=promotion)
            else:
                yield Move(square, one_step)
                two_step = square.offset(0, 2 * direction)
                if square.rank == start_rank and two_step and self.piece_at(two_step) is None:
                    yield Move(square, two_step)

        for file_delta in (-1, 1):
            capture_square = square.offset(file_delta, direction)
            if capture_square is None:
                continue
            occupant = self.piece_at(capture_square)
            if occupant and occupant.color is not piece.color:
                if capture_square.rank == promotion_rank:
                    for promotion in self._promotion_pieces():
                        yield Move(square, capture_square, promotion=promotion)
                else:
                    yield Move(square, capture_square)
                continue
            if self.en_passant_target == capture_square:
                captured_square = Square(capture_square.file, square.rank)
                captured_piece = self.piece_at(captured_square)
                if captured_piece and captured_piece.color is not piece.color and captured_piece.piece_type is PieceType.PAWN:
                    yield Move(square, capture_square, is_en_passant=True)

    def _knight_moves(self, square: Square, piece: Piece) -> Iterable[Move]:
        for file_delta, rank_delta in KNIGHT_OFFSETS:
            target = square.offset(file_delta, rank_delta)
            if target is None:
                continue
            occupant = self.piece_at(target)
            if occupant is None or occupant.color is not piece.color:
                yield Move(square, target)

    def _sliding_moves(self, square: Square, piece: Piece) -> Iterable[Move]:
        directions = SLIDING_DIRECTIONS[piece.piece_type]
        for file_delta, rank_delta in directions:
            current = square
            while True:
                current = current.offset(file_delta, rank_delta)
                if current is None:
                    break
                occupant = self.piece_at(current)
                if occupant is None:
                    yield Move(square, current)
                    continue
                if occupant.color is not piece.color:
                    yield Move(square, current)
                break

    def _king_moves(self, square: Square, piece: Piece) -> Iterable[Move]:
        for file_delta, rank_delta in KING_OFFSETS:
            target = square.offset(file_delta, rank_delta)
            if target is None:
                continue
            occupant = self.piece_at(target)
            if occupant is None or occupant.color is not piece.color:
                yield Move(square, target)

        yield from self._castling_moves(square, piece)

    def _castling_moves(self, square: Square, piece: Piece) -> Iterable[Move]:
        if piece.color is Color.WHITE:
            king_start = WHITE_KING_FROM
            kingside_rook = WHITE_KING_ROOK
            queenside_rook = WHITE_QUEEN_ROOK
            kingside_target = Square.from_algebraic("g1")
            queenside_target = Square.from_algebraic("c1")
            kingside_through = [Square.from_algebraic("f1"), kingside_target]
            queenside_through = [Square.from_algebraic("d1"), queenside_target]
            path_kingside = [Square.from_algebraic("f1"), Square.from_algebraic("g1")]
            path_queenside = [Square.from_algebraic("b1"), Square.from_algebraic("c1"), Square.from_algebraic("d1")]
            rights_kingside = self.castling_rights.white_kingside
            rights_queenside = self.castling_rights.white_queenside
            attack_color = Color.BLACK
        else:
            king_start = BLACK_KING_FROM
            kingside_rook = BLACK_KING_ROOK
            queenside_rook = BLACK_QUEEN_ROOK
            kingside_target = Square.from_algebraic("g8")
            queenside_target = Square.from_algebraic("c8")
            kingside_through = [Square.from_algebraic("f8"), kingside_target]
            queenside_through = [Square.from_algebraic("d8"), queenside_target]
            path_kingside = [Square.from_algebraic("f8"), Square.from_algebraic("g8")]
            path_queenside = [Square.from_algebraic("b8"), Square.from_algebraic("c8"), Square.from_algebraic("d8")]
            rights_kingside = self.castling_rights.black_kingside
            rights_queenside = self.castling_rights.black_queenside
            attack_color = Color.WHITE

        if square != king_start:
            return
        if self.is_square_attacked(square, attack_color):
            return

        rook = self.piece_at(kingside_rook)
        if (
            rights_kingside
            and rook
            and rook.color is piece.color
            and rook.piece_type is PieceType.ROOK
            and all(self.piece_at(target) is None for target in path_kingside)
            and all(not self.is_square_attacked(target, attack_color) for target in kingside_through)
        ):
            yield Move(square, kingside_target, is_kingside_castle=True)

        rook = self.piece_at(queenside_rook)
        if (
            rights_queenside
            and rook
            and rook.color is piece.color
            and rook.piece_type is PieceType.ROOK
            and all(self.piece_at(target) is None for target in path_queenside)
            and all(not self.is_square_attacked(target, attack_color) for target in queenside_through)
        ):
            yield Move(square, queenside_target, is_queenside_castle=True)

    def _promotion_pieces(self) -> Tuple[PieceType, ...]:
        return (PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT)

    def _apply_move_unchecked(self, move: Move) -> None:
        moving_piece = self.piece_at(move.from_square)
        if moving_piece is None:
            raise ValueError(f"No piece on {move.from_square}")

        captured_piece: Optional[Piece] = None
        captured_square = move.to_square
        if move.is_en_passant:
            captured_square = Square(move.to_square.file, move.from_square.rank)
            captured_piece = self.piece_at(captured_square)
            self.remove_piece(captured_square)
        else:
            captured_piece = self.piece_at(move.to_square)

        self.remove_piece(move.from_square)

        if move.is_kingside_castle or move.is_queenside_castle:
            self._apply_castling_rook_move(moving_piece.color, move)

        promoted_piece = moving_piece
        if moving_piece.piece_type is PieceType.PAWN and move.to_square.rank in (0, 7):
            promotion = move.promotion if move.promotion is not None else PieceType.QUEEN
            promoted_piece = Piece(moving_piece.color, promotion)

        self.set_piece(move.to_square, promoted_piece)

        self._update_castling_rights_after_move(moving_piece, move.from_square, captured_piece, captured_square)

        if moving_piece.piece_type is PieceType.PAWN and abs(move.to_square.rank - move.from_square.rank) == 2:
            middle_rank = (move.to_square.rank + move.from_square.rank) // 2
            self.en_passant_target = Square(move.from_square.file, middle_rank)
        else:
            self.en_passant_target = None

        self.side_to_move = self.side_to_move.opposite
        self.move_history.append(move)

    def _apply_castling_rook_move(self, color: Color, move: Move) -> None:
        if color is Color.WHITE:
            if move.is_kingside_castle:
                rook_from = WHITE_KING_ROOK
                rook_to = Square.from_algebraic("f1")
            else:
                rook_from = WHITE_QUEEN_ROOK
                rook_to = Square.from_algebraic("d1")
        else:
            if move.is_kingside_castle:
                rook_from = BLACK_KING_ROOK
                rook_to = Square.from_algebraic("f8")
            else:
                rook_from = BLACK_QUEEN_ROOK
                rook_to = Square.from_algebraic("d8")
        rook = self.remove_piece(rook_from)
        if rook is None:
            raise ValueError("Castling rook is missing")
        self.set_piece(rook_to, rook)

    def _update_castling_rights_after_move(
        self,
        moving_piece: Piece,
        from_square: Square,
        captured_piece: Optional[Piece],
        captured_square: Square,
    ) -> None:
        if moving_piece.piece_type is PieceType.KING:
            if moving_piece.color is Color.WHITE:
                self.castling_rights.white_kingside = False
                self.castling_rights.white_queenside = False
            else:
                self.castling_rights.black_kingside = False
                self.castling_rights.black_queenside = False
        elif moving_piece.piece_type is PieceType.ROOK:
            if from_square == WHITE_KING_ROOK:
                self.castling_rights.white_kingside = False
            elif from_square == WHITE_QUEEN_ROOK:
                self.castling_rights.white_queenside = False
            elif from_square == BLACK_KING_ROOK:
                self.castling_rights.black_kingside = False
            elif from_square == BLACK_QUEEN_ROOK:
                self.castling_rights.black_queenside = False

        if captured_piece and captured_piece.piece_type is PieceType.ROOK:
            if captured_square == WHITE_KING_ROOK:
                self.castling_rights.white_kingside = False
            elif captured_square == WHITE_QUEEN_ROOK:
                self.castling_rights.white_queenside = False
            elif captured_square == BLACK_KING_ROOK:
                self.castling_rights.black_kingside = False
            elif captured_square == BLACK_QUEEN_ROOK:
                self.castling_rights.black_queenside = False

    def __str__(self) -> str:
        rows: list[str] = []
        for rank in range(BOARD_SIZE - 1, -1, -1):
            row = []
            for file in range(BOARD_SIZE):
                piece = self.piece_at(Square(file=file, rank=rank))
                row.append(piece.symbol() if piece else ".")
            rows.append(f"{rank + 1} {' '.join(row)}")
        rows.append("  a b c d e f g h")
        return "\n".join(rows)

