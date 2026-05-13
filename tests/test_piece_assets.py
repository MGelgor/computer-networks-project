import unittest
from pathlib import Path

from client.piece_assets import build_piece_image_paths, piece_symbol_to_filename


class PieceAssetTests(unittest.TestCase):
    def test_piece_symbol_to_filename_maps_white_and_black(self) -> None:
        self.assertEqual(piece_symbol_to_filename("K"), "Chess_klt60.png")
        self.assertEqual(piece_symbol_to_filename("q"), "Chess_qdt60.png")
        self.assertEqual(piece_symbol_to_filename("P"), "Chess_plt60.png")
        self.assertEqual(piece_symbol_to_filename("n"), "Chess_ndt60.png")

    def test_build_piece_image_paths_finds_expected_files(self) -> None:
        image_dir = Path("/Users/gelgor/Documents/Github/computer-networks-project/images")
        paths = build_piece_image_paths(image_dir)
        self.assertEqual(paths["K"].name, "Chess_klt60.png")
        self.assertEqual(paths["k"].name, "Chess_kdt60.png")
        self.assertEqual(paths["Q"].name, "Chess_qlt60.png")
        self.assertEqual(paths["q"].name, "Chess_qdt60.png")
        self.assertEqual(paths["P"].name, "Chess_plt60.png")
        self.assertEqual(paths["p"].name, "Chess_pdt60.png")


if __name__ == "__main__":
    unittest.main()

