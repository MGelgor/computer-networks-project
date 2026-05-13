from __future__ import annotations

import secrets
import socket
import socketserver
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, cast

from shared.chess import Board, Color, GameResult, Move
from shared.protocol import MessageEnvelope, MessageType


@dataclass
class ClientConnection:
    socket: socket.socket
    address: Tuple[str, int]
    lock: threading.Lock = field(default_factory=threading.Lock)
    game_id: Optional[str] = None
    color: Optional[Color] = None

    def send(self, envelope: MessageEnvelope) -> None:
        payload = envelope.to_json().encode("utf-8") + b"\n"
        with self.lock:
            self.socket.sendall(payload)

    def close(self) -> None:
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.socket.close()
        except OSError:
            pass


@dataclass
class GameSession:
    game_id: str
    board: Board = field(default_factory=Board.initial)
    white: Optional[ClientConnection] = None
    black: Optional[ClientConnection] = None

    def player_for_color(self, color: Color) -> Optional[ClientConnection]:
        return self.white if color is Color.WHITE else self.black

    def opponent_for(self, connection: ClientConnection) -> Optional[ClientConnection]:
        if connection.color is Color.WHITE:
            return self.black
        if connection.color is Color.BLACK:
            return self.white
        return None

    def is_full(self) -> bool:
        return self.white is not None and self.black is not None


class ChessServerState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.games: Dict[str, GameSession] = {}

    def handle_message(self, connection: ClientConnection, envelope: MessageEnvelope) -> None:
        if envelope.type is MessageType.CREATE_GAME:
            self._handle_create_game(connection)
        elif envelope.type is MessageType.JOIN_GAME:
            self._handle_join_game(connection, str(envelope.payload.get("game_id", "")))
        elif envelope.type is MessageType.MOVE_REQUEST:
            self._handle_move_request(
                connection,
                str(envelope.payload.get("game_id", "")),
                str(envelope.payload.get("uci", "")),
            )
        else:
            connection.send(
                MessageEnvelope(
                    type=MessageType.ERROR,
                    payload={"reason": f"Unsupported message type: {envelope.type.value}"},
                )
            )

    def _handle_create_game(self, connection: ClientConnection) -> None:
        with self.lock:
            game_id = secrets.token_hex(3).upper()
            while game_id in self.games:
                game_id = secrets.token_hex(3).upper()
            session = GameSession(game_id=game_id, white=connection)
            self.games[game_id] = session
            connection.game_id = game_id
            connection.color = Color.WHITE
            payload = {
                "game_id": game_id,
                "color": connection.color.value,
                "status": "waiting_for_opponent",
                "board_text": str(session.board),
            }
        connection.send(MessageEnvelope(type=MessageType.GAME_CREATED, payload=payload))

    def _handle_join_game(self, connection: ClientConnection, game_id: str) -> None:
        if not game_id:
            connection.send(MessageEnvelope(type=MessageType.ERROR, payload={"reason": "Missing game_id"}))
            return

        with self.lock:
            session = self.games.get(game_id)
            if session is None:
                connection.send(MessageEnvelope(type=MessageType.ERROR, payload={"reason": "Game not found"}))
                return
            if session.is_full():
                connection.send(MessageEnvelope(type=MessageType.ERROR, payload={"reason": "Game is full"}))
                return

            session.black = connection
            connection.game_id = game_id
            connection.color = Color.BLACK
            white_payload = {
                "game_id": game_id,
                "color": Color.WHITE.value,
                "board_text": str(session.board),
                "side_to_move": session.board.side_to_move.value,
                "status": "in_game",
            }
            black_payload = {
                "game_id": game_id,
                "color": Color.BLACK.value,
                "board_text": str(session.board),
                "side_to_move": session.board.side_to_move.value,
                "status": "in_game",
            }
            white_connection = session.white
            black_connection = session.black

        if white_connection is not None:
            white_connection.send(MessageEnvelope(type=MessageType.GAME_START, payload=white_payload))
        if black_connection is not None:
            black_connection.send(MessageEnvelope(type=MessageType.GAME_START, payload=black_payload))

    def _handle_move_request(self, connection: ClientConnection, game_id: str, uci: str) -> None:
        if not game_id:
            connection.send(MessageEnvelope(type=MessageType.MOVE_REJECTED, payload={"reason": "Missing game_id"}))
            return
        if not uci:
            connection.send(MessageEnvelope(type=MessageType.MOVE_REJECTED, payload={"reason": "Missing move"}))
            return

        with self.lock:
            session = self.games.get(game_id)
            if session is None:
                connection.send(MessageEnvelope(type=MessageType.MOVE_REJECTED, payload={"reason": "Game not found"}))
                return
            if connection.color is None or connection.game_id != game_id:
                connection.send(MessageEnvelope(type=MessageType.MOVE_REJECTED, payload={"reason": "Not part of this game"}))
                return
            if connection.color is not session.board.side_to_move:
                connection.send(
                    MessageEnvelope(
                        type=MessageType.MOVE_REJECTED,
                        payload={"reason": "Not your turn"},
                    )
                )
                return
            try:
                move = Move.from_uci(uci)
                session.board.push(move)
            except Exception as exc:
                connection.send(
                    MessageEnvelope(
                        type=MessageType.MOVE_REJECTED,
                        payload={"reason": str(exc)},
                    )
                )
                return

            accepted_payload = {
                "game_id": game_id,
                "uci": move.to_uci(),
                "board_text": str(session.board),
                "side_to_move": session.board.side_to_move.value,
                "result": session.board.game_result.value,
            }
            white_connection = session.white
            black_connection = session.black
            game_over_payload = None
            if session.board.game_result is not GameResult.ONGOING:
                game_over_payload = {
                    "game_id": game_id,
                    "result": session.board.game_result.value,
                    "board_text": str(session.board),
                }

        message = MessageEnvelope(type=MessageType.MOVE_ACCEPTED, payload=accepted_payload)
        for target in (white_connection, black_connection):
            if target is not None:
                target.send(message)
        if game_over_payload is not None:
            end_message = MessageEnvelope(type=MessageType.GAME_END, payload=game_over_payload)
            for target in (white_connection, black_connection):
                if target is not None:
                    target.send(end_message)

    def disconnect(self, connection: ClientConnection) -> None:
        with self.lock:
            game_id = connection.game_id
            if not game_id:
                return
            session = self.games.get(game_id)
            if session is None:
                return
            if session.white is connection:
                session.white = None
            if session.black is connection:
                session.black = None
            if session.white is None and session.black is None:
                self.games.pop(game_id, None)
            else:
                opponent = session.opponent_for(connection)
                if opponent is not None:
                    try:
                        opponent.send(
                            MessageEnvelope(
                                type=MessageType.GAME_END,
                                payload={
                                    "game_id": game_id,
                                    "result": GameResult.DRAW.value,
                                    "reason": "opponent_disconnected",
                                    "board_text": str(session.board),
                                },
                            )
                        )
                    except OSError:
                        pass
                self.games.pop(game_id, None)


class ChessRequestHandler(socketserver.StreamRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.connection_state = ClientConnection(socket=self.request, address=self.client_address)

    def handle(self) -> None:
        server = cast(ChessTCPServer, self.server)
        while True:
            raw_line = self.rfile.readline()
            if not raw_line:
                break
            try:
                envelope = MessageEnvelope.from_json(raw_line.decode("utf-8").strip())
            except Exception as exc:
                self.connection_state.send(
                    MessageEnvelope(type=MessageType.ERROR, payload={"reason": f"Invalid JSON: {exc}"})
                )
                continue
            server.logic.handle_message(self.connection_state, envelope)

    def finish(self) -> None:
        server = cast(ChessTCPServer, self.server)
        try:
            server.logic.disconnect(self.connection_state)
        finally:
            try:
                self.connection_state.close()
            finally:
                super().finish()


class ChessTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address: Tuple[str, int]) -> None:
        super().__init__(server_address, ChessRequestHandler)  # type: ignore[arg-type]
        self.logic = ChessServerState()


class LocalServerHandle:
    def __init__(self, server: ChessTCPServer, thread: threading.Thread) -> None:
        self.server = server
        self.thread = thread

    @property
    def address(self) -> Tuple[str, int]:
        host, port = self.server.server_address
        return host, port

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2.0)


def start_local_server(host: str = "127.0.0.1", port: int = 0) -> LocalServerHandle:
    server = ChessTCPServer((host, port))
    thread = threading.Thread(target=server.serve_forever, name="ChessTCPServer", daemon=True)
    thread.start()
    return LocalServerHandle(server, thread)


