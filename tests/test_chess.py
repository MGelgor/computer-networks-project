import unittest

from shared.chess import Board, CastlingRights, Color, GameResult, Move, Piece, PieceType, Square


class ChessTests(unittest.TestCase):
    def test_square_round_trip(self) -> None:
        square = Square.from_algebraic("e4")
        self.assertEqual(square.file, 4)
        self.assertEqual(square.rank, 3)
        self.assertEqual(square.to_algebraic(), "e4")

    def test_initial_position_has_twenty_legal_moves(self) -> None:
        board = Board.initial()
        moves = board.legal_moves()
        self.assertEqual(board.side_to_move, Color.WHITE)
        self.assertEqual(len(moves), 20)
        self.assertIn(Move.from_uci("e2e4"), moves)
        self.assertIn(Move.from_uci("g1f3"), moves)

    def test_pawn_movement_and_capture(self) -> None:
        board = Board.from_piece_map(
            {
                "e2": Piece(Color.WHITE, PieceType.PAWN),
                "d3": Piece(Color.BLACK, PieceType.KNIGHT),
            },
            side_to_move=Color.WHITE,
        )
        moves = set(board.legal_moves())
        self.assertIn(Move.from_uci("e2e3"), moves)
        self.assertIn(Move.from_uci("e2e4"), moves)
        self.assertIn(Move.from_uci("e2d3"), moves)

    def test_pawn_blocked_cannot_move_forward(self) -> None:
        board = Board.from_piece_map(
            {
                "e2": Piece(Color.WHITE, PieceType.PAWN),
                "e3": Piece(Color.BLACK, PieceType.KNIGHT),
            },
            side_to_move=Color.WHITE,
        )
        moves = board.legal_moves()
        self.assertNotIn(Move.from_uci("e2e3"), moves)
        self.assertNotIn(Move.from_uci("e2e4"), moves)

    def test_en_passant_is_generated_and_applied(self) -> None:
        board = Board.from_piece_map(
            {
                "e5": Piece(Color.WHITE, PieceType.PAWN),
                "d5": Piece(Color.BLACK, PieceType.PAWN),
                "a1": Piece(Color.WHITE, PieceType.KING),
                "h8": Piece(Color.BLACK, PieceType.KING),
            },
            side_to_move=Color.WHITE,
            en_passant_target="d6",
        )
        move = Move.from_uci("e5d6")
        self.assertTrue(
            any(
                candidate.from_square == move.from_square
                and candidate.to_square == move.to_square
                and candidate.is_en_passant
                for candidate in board.legal_moves()
            )
        )
        board.push(move)
        self.assertEqual(board.piece_at(Square.from_algebraic("d6")), Piece(Color.WHITE, PieceType.PAWN))
        self.assertIsNone(board.piece_at(Square.from_algebraic("d5")))

    def test_castling_moves_are_available_when_clear(self) -> None:
        board = Board.from_piece_map(
            {
                "e1": Piece(Color.WHITE, PieceType.KING),
                "a1": Piece(Color.WHITE, PieceType.ROOK),
                "h1": Piece(Color.WHITE, PieceType.ROOK),
                "e8": Piece(Color.BLACK, PieceType.KING),
            },
            side_to_move=Color.WHITE,
            castling_rights=CastlingRights(white_kingside=True, white_queenside=True),
        )
        moves = set(board.legal_moves())
        self.assertIn(
            Move(
                from_square=Square.from_algebraic("e1"),
                to_square=Square.from_algebraic("g1"),
                is_kingside_castle=True,
            ),
            moves,
        )
        self.assertIn(
            Move(
                from_square=Square.from_algebraic("e1"),
                to_square=Square.from_algebraic("c1"),
                is_queenside_castle=True,
            ),
            moves,
        )

    def test_castling_is_blocked_if_path_is_attacked(self) -> None:
        board = Board.from_piece_map(
            {
                "e1": Piece(Color.WHITE, PieceType.KING),
                "h1": Piece(Color.WHITE, PieceType.ROOK),
                "e8": Piece(Color.BLACK, PieceType.KING),
                "f8": Piece(Color.BLACK, PieceType.ROOK),
            },
            side_to_move=Color.WHITE,
            castling_rights=CastlingRights(white_kingside=True),
        )
        self.assertTrue(all(not move.is_kingside_castle for move in board.legal_moves()))

    def test_check_detection_checkmate_and_stalemate(self) -> None:
        checkmate = Board.from_piece_map(
            {
                "h1": Piece(Color.WHITE, PieceType.KING),
                "g2": Piece(Color.BLACK, PieceType.QUEEN),
                "f3": Piece(Color.BLACK, PieceType.KING),
            },
            side_to_move=Color.WHITE,
        )
        self.assertTrue(checkmate.is_in_check(Color.WHITE))
        self.assertTrue(checkmate.is_checkmate(Color.WHITE))
        self.assertEqual(checkmate.legal_moves(Color.WHITE), [])

        stalemate = Board.from_piece_map(
            {
                "h1": Piece(Color.WHITE, PieceType.KING),
                "g3": Piece(Color.BLACK, PieceType.QUEEN),
                "f3": Piece(Color.BLACK, PieceType.KING),
            },
            side_to_move=Color.WHITE,
        )
        self.assertFalse(stalemate.is_in_check(Color.WHITE))
        self.assertTrue(stalemate.is_stalemate(Color.WHITE))
        self.assertEqual(stalemate.legal_moves(Color.WHITE), [])

    def test_turn_logic_rejects_wrong_color_and_flips_after_legal_move(self) -> None:
        board = Board.initial()
        with self.assertRaises(ValueError):
            board.push(Move.from_uci("e7e5"))

        board.push(Move.from_uci("e2e4"))
        self.assertEqual(board.side_to_move, Color.BLACK)
        self.assertEqual(board.piece_at(Square.from_algebraic("e4")), Piece(Color.WHITE, PieceType.PAWN))

    def test_promotion_defaults_to_queen_when_not_explicit(self) -> None:
        board = Board.from_piece_map(
            {
                "e7": Piece(Color.WHITE, PieceType.PAWN),
                "a1": Piece(Color.WHITE, PieceType.KING),
                "h8": Piece(Color.BLACK, PieceType.KING),
            },
            side_to_move=Color.WHITE,
        )
        board.push(Move.from_uci("e7e8"))
        self.assertEqual(board.piece_at(Square.from_algebraic("e8")), Piece(Color.WHITE, PieceType.QUEEN))
        self.assertEqual(board.game_result, GameResult.ONGOING)


if __name__ == "__main__":
    unittest.main()

