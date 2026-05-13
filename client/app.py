from __future__ import annotations

import argparse

from client.lan_client import LanChessClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LAN chess client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--name", default="player")
    parser.add_argument("--ui", choices=("console", "qt"), default="console")
    args = parser.parse_args()

    if args.ui == "qt":
        from client.qt_app import run_qt_client

        try:
            run_qt_client(host=args.host, port=args.port, name=args.name)
        except RuntimeError as exc:
            print(str(exc))
        return

    client = LanChessClient(host=args.host, port=args.port, name=args.name)
    client.interactive_loop()


if __name__ == "__main__":
    main()

