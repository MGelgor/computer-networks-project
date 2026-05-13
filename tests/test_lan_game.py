from __future__ import annotations

import unittest

from client.lan_client import LanChessClient
from shared.protocol import MessageType
from server.local_server import start_local_server


class LanGameTests(unittest.TestCase):
    def test_two_player_lan_game_flow(self) -> None:
        handle = start_local_server()
        host, port = handle.address
        white = LanChessClient(host=host, port=port, name="white", verbose=False)
        black = LanChessClient(host=host, port=port, name="black", verbose=False)
        try:
            white.connect()
            black.connect()

            white.create_game()
            created = white.wait_for(MessageType.GAME_CREATED)
            game_id = str(created.payload["game_id"])
            self.assertEqual(white.game_id, game_id)
            self.assertEqual(white.color, "white")

            black.join_game(game_id)
            start_white = white.wait_for(MessageType.GAME_START)
            start_black = black.wait_for(MessageType.GAME_START)
            self.assertEqual(str(start_white.payload["game_id"]), game_id)
            self.assertEqual(str(start_black.payload["game_id"]), game_id)

            white.move("f2f3")
            white.wait_for(MessageType.MOVE_ACCEPTED)
            black.wait_for(MessageType.MOVE_ACCEPTED)

            black.move("e7e5")
            white.wait_for(MessageType.MOVE_ACCEPTED)
            black.wait_for(MessageType.MOVE_ACCEPTED)

            white.move("g2g4")
            white.wait_for(MessageType.MOVE_ACCEPTED)
            black.wait_for(MessageType.MOVE_ACCEPTED)

            black.move("d8h4")
            white.wait_for(MessageType.MOVE_ACCEPTED)
            black.wait_for(MessageType.MOVE_ACCEPTED)

            end_white = white.wait_for(MessageType.GAME_END)
            end_black = black.wait_for(MessageType.GAME_END)
            self.assertEqual(str(end_white.payload["result"]), "0-1")
            self.assertEqual(str(end_black.payload["result"]), "0-1")
            self.assertEqual(white.status, "game_over")
            self.assertEqual(black.status, "game_over")
        finally:
            white.close()
            black.close()
            handle.close()


if __name__ == "__main__":
    unittest.main()


