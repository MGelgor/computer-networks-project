from __future__ import annotations

from typing import List


def parse_board_text(board_text: str) -> List[List[str]]:
    """Parse the server board text into an 8x8 matrix indexed by [rank][file].

    rank index 0 is White's back rank (board row "1"), rank index 7 is Black's back rank.
    """
    matrix = [["."] * 8 for _ in range(8)]
    for raw_line in board_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 9:
            continue
        if not parts[0].isdigit():
            continue
        rank_number = int(parts[0])
        if rank_number < 1 or rank_number > 8:
            continue
        rank_index = rank_number - 1
        for file_index, token in enumerate(parts[1:]):
            matrix[rank_index][file_index] = token
    return matrix


def piece_at(matrix: List[List[str]], file_index: int, rank_index: int) -> str:
    return matrix[rank_index][file_index]

