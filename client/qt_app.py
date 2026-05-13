from __future__ import annotations

import importlib
from pathlib import Path
from typing import List, Optional, Tuple

from client.board_text import parse_board_text, piece_at
from client.lan_client import LanChessClient
from client.piece_assets import build_piece_image_paths
from shared.protocol import MessageEnvelope, MessageType


def run_qt_client(host: str, port: int, name: str) -> None:
    try:
        qtcore = importlib.import_module("PySide6.QtCore")
        qtgui = importlib.import_module("PySide6.QtGui")
        qtwidgets = importlib.import_module("PySide6.QtWidgets")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PySide6 is required for Qt mode. Install with: python3 -m pip install PySide6"
        ) from exc

    QPoint = qtcore.QPoint
    QRect = qtcore.QRect
    Qt = qtcore.Qt
    QTimer = qtcore.QTimer
    Signal = qtcore.Signal

    QColor = qtgui.QColor
    QFont = qtgui.QFont
    QPainter = qtgui.QPainter
    QPen = qtgui.QPen
    QPixmap = qtgui.QPixmap

    QApplication = qtwidgets.QApplication
    QGridLayout = qtwidgets.QGridLayout
    QHBoxLayout = qtwidgets.QHBoxLayout
    QLabel = qtwidgets.QLabel
    QLineEdit = qtwidgets.QLineEdit
    QMainWindow = qtwidgets.QMainWindow
    QMessageBox = qtwidgets.QMessageBox
    QPushButton = qtwidgets.QPushButton
    QVBoxLayout = qtwidgets.QVBoxLayout
    QWidget = qtwidgets.QWidget

    class BoardWidget(QWidget):
        move_attempted = Signal(str)

        def __init__(self, piece_pixmaps: dict[str, object]) -> None:
            super().__init__()
            self.setMinimumSize(560, 560)
            self._board: List[List[str]] = [["."] * 8 for _ in range(8)]
            self._selected: Optional[Tuple[int, int]] = None
            self._last_move: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
            self._drag_start: Optional[Tuple[int, int]] = None
            self._is_dragging = False
            self._player_color = "white"
            self._piece_pixmaps = piece_pixmaps
            self.setMouseTracking(True)

        def set_player_color(self, color: Optional[str]) -> None:
            if color in ("white", "black"):
                self._player_color = color
                self.update()

        def set_board_text(self, board_text: str) -> None:
            self._board = parse_board_text(board_text)
            self.update()

        def set_last_move_uci(self, uci: str) -> None:
            if len(uci) < 4:
                return
            from_sq = self._parse_square(uci[0:2])
            to_sq = self._parse_square(uci[2:4])
            if from_sq is None or to_sq is None:
                return
            self._last_move = (from_sq, to_sq)
            self.update()

        def mousePressEvent(self, event) -> None:  # type: ignore[override]
            if event.button() != Qt.LeftButton:
                return
            square = self._square_at(event.position().toPoint())
            if square is None:
                return
            file_index, rank_index = square
            if self._selected is None:
                piece = piece_at(self._board, file_index, rank_index)
                if piece != "." and self._is_my_piece(piece):
                    self._selected = square
                    self._drag_start = square
            else:
                if square == self._selected:
                    self._selected = None
                else:
                    self._emit_move(self._selected, square)
                    self._selected = None
            self.update()

        def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
            if not (event.buttons() & Qt.LeftButton):
                return
            if self._drag_start is None:
                return
            self._is_dragging = True

        def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
            if event.button() != Qt.LeftButton:
                return
            if self._is_dragging and self._drag_start is not None:
                target = self._square_at(event.position().toPoint())
                if target is not None and target != self._drag_start:
                    self._emit_move(self._drag_start, target)
                self._selected = None
            self._drag_start = None
            self._is_dragging = False
            self.update()

        def paintEvent(self, _event) -> None:  # type: ignore[override]
            painter = QPainter(self)
            board_rect = self.rect()
            cell = min(board_rect.width(), board_rect.height()) // 8
            left = (board_rect.width() - cell * 8) // 2
            top = (board_rect.height() - cell * 8) // 2

            light = QColor(240, 217, 181)
            dark = QColor(181, 136, 99)
            selected_color = QColor(255, 255, 128, 180)
            last_move_color = QColor(166, 206, 57, 180)

            piece_font = QFont("Arial", max(14, cell // 2), QFont.Bold)
            coord_font = QFont("Arial", max(8, cell // 6))

            for display_rank in range(8):
                for display_file in range(8):
                    file_index, rank_index = self._display_to_board(display_file, display_rank)
                    rect = QRect(left + display_file * cell, top + display_rank * cell, cell, cell)
                    base = light if (display_file + display_rank) % 2 == 0 else dark
                    painter.fillRect(rect, base)

                    if self._last_move is not None and (
                        (file_index, rank_index) == self._last_move[0] or (file_index, rank_index) == self._last_move[1]
                    ):
                        painter.fillRect(rect, last_move_color)

                    if self._selected == (file_index, rank_index):
                        painter.fillRect(rect, selected_color)

                    piece = piece_at(self._board, file_index, rank_index)
                    if piece != ".":
                        pixmap = self._piece_pixmaps.get(piece)
                        if pixmap is not None and not pixmap.isNull():
                            inset = max(2, cell // 10)
                            painter.drawPixmap(rect.adjusted(inset, inset, -inset, -inset), pixmap)
                        else:
                            painter.setFont(piece_font)
                            painter.setPen(QPen(QColor(15, 15, 15)))
                            painter.drawText(rect, Qt.AlignCenter, self._piece_symbol(piece))

            painter.setFont(coord_font)
            painter.setPen(QPen(QColor(35, 35, 35)))
            for display_file in range(8):
                file_char = chr(ord("a") + self._display_to_board(display_file, 0)[0])
                x = left + display_file * cell + 4
                y = top + cell * 8 - 4
                painter.drawText(x, y, file_char)
            for display_rank in range(8):
                rank_num = str(self._display_to_board(0, display_rank)[1] + 1)
                x = left + 4
                y = top + display_rank * cell + 14
                painter.drawText(x, y, rank_num)

        def _is_my_piece(self, piece: str) -> bool:
            if self._player_color == "white":
                return piece.isupper()
            return piece.islower()

        def _parse_square(self, algebraic: str) -> Optional[Tuple[int, int]]:
            if len(algebraic) != 2:
                return None
            file_char = algebraic[0]
            rank_char = algebraic[1]
            if file_char < "a" or file_char > "h":
                return None
            if rank_char < "1" or rank_char > "8":
                return None
            return ord(file_char) - ord("a"), int(rank_char) - 1

        def _emit_move(self, from_sq: Tuple[int, int], to_sq: Tuple[int, int]) -> None:
            from_text = f"{chr(ord('a') + from_sq[0])}{from_sq[1] + 1}"
            to_text = f"{chr(ord('a') + to_sq[0])}{to_sq[1] + 1}"
            uci = f"{from_text}{to_text}"
            piece = piece_at(self._board, from_sq[0], from_sq[1])
            if piece in ("P", "p") and to_sq[1] in (0, 7):
                uci += "q"
            self.move_attempted.emit(uci)

        def _square_at(self, point: QPoint) -> Optional[Tuple[int, int]]:
            board_rect = self.rect()
            cell = min(board_rect.width(), board_rect.height()) // 8
            left = (board_rect.width() - cell * 8) // 2
            top = (board_rect.height() - cell * 8) // 2
            x = point.x() - left
            y = point.y() - top
            if x < 0 or y < 0 or x >= cell * 8 or y >= cell * 8:
                return None
            display_file = x // cell
            display_rank = y // cell
            return self._display_to_board(display_file, display_rank)

        def _display_to_board(self, display_file: int, display_rank: int) -> Tuple[int, int]:
            if self._player_color == "white":
                return display_file, 7 - display_rank
            return 7 - display_file, display_rank

        def _piece_symbol(self, piece: str) -> str:
            symbols = {
                "K": "K",
                "Q": "Q",
                "R": "R",
                "B": "B",
                "N": "N",
                "P": "P",
                "k": "k",
                "q": "q",
                "r": "r",
                "b": "b",
                "n": "n",
                "p": "p",
            }
            return symbols.get(piece, piece)

    class ChessMainWindow(QMainWindow):
        def __init__(self, host_value: str, port_value: int, name_value: str) -> None:
            super().__init__()
            self.setWindowTitle("LAN Chess (Qt)")
            self.resize(900, 700)

            self.client = LanChessClient(host=host_value, port=port_value, name=name_value, verbose=False)

            self.host_input = QLineEdit(host_value)
            self.port_input = QLineEdit(str(port_value))
            self.name_input = QLineEdit(name_value)
            self.game_input = QLineEdit("")
            self.status_label = QLabel("Disconnected")

            self.connect_button = QPushButton("Connect")
            self.create_button = QPushButton("Create Game")
            self.join_button = QPushButton("Join Game")

            self.board_widget = BoardWidget(_load_piece_pixmaps(QPixmap))

            controls = QWidget()
            controls_layout = QGridLayout(controls)
            controls_layout.addWidget(QLabel("Host"), 0, 0)
            controls_layout.addWidget(self.host_input, 0, 1)
            controls_layout.addWidget(QLabel("Port"), 0, 2)
            controls_layout.addWidget(self.port_input, 0, 3)
            controls_layout.addWidget(QLabel("Name"), 1, 0)
            controls_layout.addWidget(self.name_input, 1, 1)
            controls_layout.addWidget(QLabel("Game ID"), 1, 2)
            controls_layout.addWidget(self.game_input, 1, 3)

            button_row = QHBoxLayout()
            button_row.addWidget(self.connect_button)
            button_row.addWidget(self.create_button)
            button_row.addWidget(self.join_button)
            button_row.addStretch(1)
            button_row.addWidget(self.status_label)

            root = QWidget()
            root_layout = QVBoxLayout(root)
            root_layout.addWidget(controls)
            root_layout.addLayout(button_row)
            root_layout.addWidget(self.board_widget, stretch=1)
            self.setCentralWidget(root)

            self.connect_button.clicked.connect(self._connect)
            self.create_button.clicked.connect(self._create_game)
            self.join_button.clicked.connect(self._join_game)
            self.board_widget.move_attempted.connect(self._on_move_attempted)

            self.timer = QTimer(self)
            self.timer.setInterval(100)
            self.timer.timeout.connect(self._poll_messages)
            self.timer.start()

        def closeEvent(self, event) -> None:  # type: ignore[override]
            self.client.close()
            super().closeEvent(event)

        def _connect(self) -> None:
            try:
                host_text = self.host_input.text().strip() or "127.0.0.1"
                port_text = int(self.port_input.text().strip())
                name_text = self.name_input.text().strip() or "player"
                self.client.host = host_text
                self.client.port = port_text
                self.client.name = name_text
                self.client.connect()
                self.status_label.setText(f"Connected to {host_text}:{port_text}")
            except Exception as exc:
                self._show_error(str(exc))

        def _create_game(self) -> None:
            try:
                self.client.create_game()
            except Exception as exc:
                self._show_error(str(exc))

        def _join_game(self) -> None:
            game_id = self.game_input.text().strip()
            if not game_id:
                self._show_error("Enter a game id to join")
                return
            try:
                self.client.join_game(game_id)
            except Exception as exc:
                self._show_error(str(exc))

        def _on_move_attempted(self, uci: str) -> None:
            try:
                self.client.move(uci)
            except Exception as exc:
                self._show_error(str(exc))

        def _poll_messages(self) -> None:
            for envelope in self.client.drain_messages():
                self._apply_message(envelope)

        def _apply_message(self, envelope: MessageEnvelope) -> None:
            payload = envelope.payload
            if envelope.type is MessageType.GAME_CREATED:
                self.game_input.setText(str(payload.get("game_id", "")))
                self.board_widget.set_player_color(str(payload.get("color", "white")))
                self.board_widget.set_board_text(str(payload.get("board_text", "")))
                self.status_label.setText("Waiting for opponent")
            elif envelope.type is MessageType.GAME_START:
                self.game_input.setText(str(payload.get("game_id", "")))
                self.board_widget.set_player_color(str(payload.get("color", "white")))
                self.board_widget.set_board_text(str(payload.get("board_text", "")))
                self.status_label.setText(f"In game as {payload.get('color')}")
            elif envelope.type is MessageType.MOVE_ACCEPTED:
                self.board_widget.set_board_text(str(payload.get("board_text", "")))
                self.board_widget.set_last_move_uci(str(payload.get("uci", "")))
                side_to_move = str(payload.get("side_to_move", ""))
                self.status_label.setText(f"Move accepted. Turn: {side_to_move}")
            elif envelope.type is MessageType.MOVE_REJECTED:
                self.status_label.setText(f"Move rejected: {payload.get('reason', '')}")
            elif envelope.type is MessageType.GAME_END:
                self.board_widget.set_board_text(str(payload.get("board_text", "")))
                self.status_label.setText(f"Game end: {payload.get('result', '')}")
            elif envelope.type is MessageType.ERROR:
                self._show_error(str(payload.get("reason", "Unknown error")))

        def _show_error(self, text: str) -> None:
            self.status_label.setText(text)
            QMessageBox.warning(self, "LAN Chess", text)

    app = QApplication([])
    window = ChessMainWindow(host, port, name)
    window.show()
    app.exec()


def _load_piece_pixmaps(QPixmapClass: object) -> dict[str, object]:
    image_dir = Path(__file__).resolve().parents[1] / "images"
    image_paths = build_piece_image_paths(image_dir)
    pixmaps: dict[str, object] = {}
    for symbol, path in image_paths.items():
        pixmap = QPixmapClass(str(path))
        if pixmap is not None:
            pixmaps[symbol] = pixmap
    return pixmaps



