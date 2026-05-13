from shared.chess import Board


def main() -> None:
    board = Board.initial()
    print(board)
    print()
    moves = board.legal_moves()
    print(f"Legal opening moves for white: {len(moves)}")
    print(", ".join(move.to_uci() for move in moves))


if __name__ == "__main__":
    main()
