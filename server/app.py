from __future__ import annotations

import argparse
import time

from server.local_server import start_local_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LAN chess server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()

    handle = start_local_server(host=args.host, port=args.port)
    host, port = handle.address
    print(f"LAN chess server listening on {host}:{port}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        handle.close()


if __name__ == "__main__":
    main()

