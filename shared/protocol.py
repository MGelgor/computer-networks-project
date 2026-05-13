from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MessageType(str, Enum):
    CREATE_GAME = "CreateGame"
    JOIN_GAME = "JoinGame"
    MOVE_REQUEST = "MoveRequest"
    MOVE_ACCEPTED = "MoveAccepted"
    MOVE_REJECTED = "MoveRejected"
    GAME_START = "GameStart"
    GAME_END = "GameEnd"


@dataclass(frozen=True)
class MessageEnvelope:
    type: MessageType
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None
    protocol_version: int = 1

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type.value,
                "request_id": self.request_id,
                "payload": self.payload,
                "protocol_version": self.protocol_version,
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, text: str) -> "MessageEnvelope":
        data = json.loads(text)
        return cls(
            type=MessageType(data["type"]),
            request_id=data.get("request_id"),
            payload=dict(data.get("payload", {})),
            protocol_version=int(data.get("protocol_version", 1)),
        )

