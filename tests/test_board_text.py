import unittest

from client.board_text import parse_board_text


class BoardTextTests(unittest.TestCase):
    def test_parse_board_text_reads_ranks_and_files(self) -> None:
        board_text = "\n".join(
            [
                "8 r n b q k b n r",
                "7 p p p p p p p p",
                "6 . . . . . . . .",
                "5 . . . . . . . .",
                "4 . . . . . . . .",
                "3 . . . . . . . .",
                "2 P P P P P P P P",
                "1 R N B Q K B N R",
                "  a b c d e f g h",
            ]
        )
        matrix = parse_board_text(board_text)
        self.assertEqual(matrix[0][0], "R")
        self.assertEqual(matrix[0][4], "K")
        self.assertEqual(matrix[7][4], "k")
        self.assertEqual(matrix[6][0], "p")
        self.assertEqual(matrix[1][0], "P")


if __name__ == "__main__":
    unittest.main()

