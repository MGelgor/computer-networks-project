from __future__ import annotations

import queue
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from shared.protocol import MessageEnvelope, MessageType


@dataclass
class LanChessClient:
    host: str = "127.0.0.1"
    port: int = 8765
    name: str = "player"
    verbose: bool = True
    socket: Optional[socket.socket] = field(default=None, init=False)
    game_id: Optional[str] = field(default=None, init=False)
    color: Optional[str] = field(default=None, init=False)
    board_text: str = field(default="", init=False)
    status: str = field(default="disconnected", init=False)
    received: "queue.Queue[MessageEnvelope]" = field(default_factory=queue.Queue, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _listener: Optional[threading.Thread] = field(default=None, init=False)
    _send_lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def connect(self) -> None:
        if self.socket is not None:
            return
        self.socket = socket.create_connection((self.host, self.port), timeout=5.0)
        self.socket.settimeout(0.5)
        self._stop_event.clear()
        self._listener = threading.Thread(target=self._listen_loop, name=f"LanChessClient-{self.name}", daemon=True)
        self._listener.start()
        self.status = "connected"
        self._log(f"Connected to {self.host}:{self.port}")

    def close(self) -> None:
        self._stop_event.set()
        if self.socket is not None:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.socket.close()
            except OSError:
                pass
        if self._listener is not None:
            self._listener.join(timeout=2.0)
        self.socket = None
        self.status = "closed"

    def create_game(self) -> None:
        self.send(MessageEnvelope(type=MessageType.CREATE_GAME, payload={"name": self.name}))

    def join_game(self, game_id: str) -> None:
        self.send(MessageEnvelope(type=MessageType.JOIN_GAME, payload={"game_id": game_id, "name": self.name}))

    def move(self, uci: str) -> None:
        if self.game_id is None:
            raise RuntimeError("No active game. Create or join a game first.")
        self.send(MessageEnvelope(type=MessageType.MOVE_REQUEST, payload={"game_id": self.game_id, "uci": uci}))

    def send(self, envelope: MessageEnvelope) -> None:
        if self.socket is None:
            raise RuntimeError("Client is not connected")
        payload = envelope.to_json().encode("utf-8") + b"\n"
        with self._send_lock:
            self.socket.sendall(payload)

    def wait_for(self, message_type: MessageType, timeout: float = 2.0) -> MessageEnvelope:
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for {message_type.value}")
            envelope = self.received.get(timeout=remaining)
            if envelope.type is message_type:
                return envelope

    def show(self) -> str:
        lines = [
            f"status: {self.status}",
            f"game_id: {self.game_id}",
            f"color: {self.color}",
            "board:",
            self.board_text or "<no board yet>",
        ]
        output = "\n".join(lines)
        print(output)
        return output

    def interactive_loop(self) -> None:
        self.connect()
        print("Commands: create, join <game_id>, move <uci>, show, quit")
        try:
            while True:
                command = input(f"{self.name}> ").strip()
                if not command:
                    continue
                if command == "quit":
                    break
                if command == "create":
                    self.create_game()
                    continue
                if command.startswith("join "):
                    self.join_game(command.split(maxsplit=1)[1])
                    continue
                if command.startswith("move "):
                    self.move(command.split(maxsplit=1)[1])
                    continue
                if command == "show":
                    self.show()
                    continue
                print("Unknown command")
        finally:
            self.close()

    def _listen_loop(self) -> None:
        if self.socket is None:
            return
        buffer = b""
        while not self._stop_event.is_set():
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    raw_line, buffer = buffer.split(b"\n", 1)
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    envelope = MessageEnvelope.from_json(line)
                    self.received.put(envelope)
                    self._handle_message(envelope)
            except socket.timeout:
                continue
            except OSError:
                break
        self._stop_event.set()
        self.status = "disconnected"

    def _handle_message(self, envelope: MessageEnvelope) -> None:
        payload = envelope.payload
        if envelope.type is MessageType.GAME_CREATED:
            self.game_id = str(payload.get("game_id"))
            self.color = str(payload.get("color"))
            self.board_text = str(payload.get("board_text", ""))
            self.status = str(payload.get("status", "waiting_for_opponent"))
            self._log(f"Game created: {self.game_id} (color={self.color})")
        elif envelope.type is MessageType.GAME_START:
            self.game_id = str(payload.get("game_id"))
            self.color = str(payload.get("color"))
            self.board_text = str(payload.get("board_text", ""))
            self.status = str(payload.get("status", "in_game"))
            self._log(f"Game started: {self.game_id} (color={self.color})")
            self._log(self.board_text)
        elif envelope.type is MessageType.MOVE_ACCEPTED:
            self.board_text = str(payload.get("board_text", self.board_text))
            self.status = "in_game"
            self._log(f"Move accepted: {payload.get('uci')}")
            self._log(self.board_text)
        elif envelope.type is MessageType.MOVE_REJECTED:
            self._log(f"Move rejected: {payload.get('reason')}")
        elif envelope.type is MessageType.GAME_END:
            self.board_text = str(payload.get("board_text", self.board_text))
            self.status = "game_over"
            self._log(f"Game ended: {payload.get('result')} ({payload.get('reason', 'normal')})")
            self._log(self.board_text)
        elif envelope.type is MessageType.ERROR:
            self._log(f"Error: {payload.get('reason')}")
        elif envelope.type is MessageType.STATE:
            self.status = str(payload.get("status", self.status))
            self.board_text = str(payload.get("board_text", self.board_text))
            self._log(f"State: {self.status}")
        else:
            self._log(f"Unhandled message: {envelope.type.value}")

    def _log(self, text: str) -> None:
        if self.verbose:
            print(f"[{self.name}] {text}")


