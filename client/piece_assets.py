from __future__ import annotations

from pathlib import Path
from typing import Dict

PIECE_SYMBOLS = "KQRBNPkqrbnp"


def piece_symbol_to_filename(symbol: str) -> str:
    symbol = symbol.strip()
    if len(symbol) != 1 or symbol not in PIECE_SYMBOLS:
        raise ValueError(f"Unsupported piece symbol: {symbol!r}")
    piece_letter = symbol.lower()
    side_letter = "lt" if symbol.isupper() else "dt"
    return f"Chess_{piece_letter}{side_letter}60.png"


def build_piece_image_paths(image_dir: Path) -> Dict[str, Path]:
    paths: Dict[str, Path] = {}
    for symbol in PIECE_SYMBOLS:
        path = image_dir / piece_symbol_to_filename(symbol)
        if path.exists():
            paths[symbol] = path
    return paths

