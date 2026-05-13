# Current Connection Model

This document explains the **current** multiplayer connection implementation in the project as it exists today.

The goal is to make the networking model completely explicit so it can serve as the baseline for later LAN and AWS work.

---

## 1) What the current connection actually is

The current multiplayer connection is:

- **Transport:** raw TCP sockets
- **Protocol:** newline-delimited JSON messages
- **Server model:** one server process, threaded per client connection
- **Game model:** the server is authoritative and owns the board state
- **Client model:** clients request actions and render server-approved state

This is **not** WebSocket-based yet.
It is a simpler socket protocol that is easy to debug locally and works well as an early prototype.

---

## 2) Files involved

The current connection is implemented across these files:

- `server/local_server.py`
- `client/lan_client.py`
- `client/app.py`
- `client/qt_app.py`
- `shared/protocol.py`
- `shared/chess/board.py`

Their roles are:

- `server/local_server.py` controls the server-side session logic.
- `client/lan_client.py` controls the socket client and message parsing.
- `shared/protocol.py` defines the JSON envelope and message types.
- `shared/chess/board.py` validates moves and updates the board.
- `client/app.py` starts either console mode or Qt mode.
- `client/qt_app.py` uses the same network client but displays the board visually.

---

## 3) Transport layer details

### 3.1 Socket type
The connection uses Python’s standard `socket` module.

On the client side:
- the client opens a TCP connection using `socket.create_connection((host, port))`

On the server side:
- the server listens with `socketserver.TCPServer`
- it handles each incoming client using a request handler

### 3.2 Framing strategy
TCP is a stream, not a message queue.
That means the code must define where one message ends and the next begins.

The current solution is:
- **each JSON message is followed by a newline (`\n`)**
- one message = one line

So the wire format is:

```text
{"type":"CreateGame",...}\n
{"type":"JoinGame",...}\n
{"type":"MoveRequest",...}\n
```

This is simple, human-readable, and easy to debug with printed logs.

### 3.3 Why newline framing matters
Without message framing, TCP could:
- split one message across multiple reads
- combine multiple messages into one read

The current code handles that by:
- reading raw bytes from the socket
- buffering them
- splitting on `\n`
- decoding each complete line separately

That makes the protocol reliable even though the underlying transport is a byte stream.

---

## 4) Protocol format

### 4.1 Envelope structure
All messages use the same envelope structure defined in `shared/protocol.py`.

The envelope looks like:

```json
{
  "type": "MoveRequest",
  "request_id": null,
  "payload": {
    "game_id": "A1B2C3",
    "uci": "e2e4"
  },
  "protocol_version": 1
}
```

### 4.2 Envelope fields

- `type`
  - the message type
  - example: `CreateGame`, `JoinGame`, `MoveRequest`

- `request_id`
  - optional correlation field
  - currently unused in the main flow, but included for future extension

- `payload`
  - a free-form JSON object carrying the actual data

- `protocol_version`
  - currently `1`
  - useful later if the protocol changes

### 4.3 Current message types
The current code uses these message types:

Client → Server:
- `CreateGame`
- `JoinGame`
- `MoveRequest`

Server → Client:
- `GameCreated`
- `GameStart`
- `MoveAccepted`
- `MoveRejected`
- `GameEnd`
- `Error`
- `State` is defined but not currently central to the flow

### 4.4 Payload expectations

#### `CreateGame`
Payload example:
```json
{ "name": "white" }
```

#### `JoinGame`
Payload example:
```json
{ "game_id": "A1B2C3", "name": "black" }
```

#### `MoveRequest`
Payload example:
```json
{ "game_id": "A1B2C3", "uci": "e2e4" }
```

#### `MoveAccepted`
Payload example:
```json
{
  "game_id": "A1B2C3",
  "uci": "e2e4",
  "board_text": "...",
  "side_to_move": "black",
  "result": "ongoing"
}
```

#### `MoveRejected`
Payload example:
```json
{ "reason": "Not your turn" }
```

#### `GameEnd`
Payload example:
```json
{
  "game_id": "A1B2C3",
  "result": "0-1",
  "board_text": "...",
  "reason": "normal"
}
```

---

## 5) Server-side connection flow

### 5.1 Server startup
`server/app.py` starts the local TCP server by calling `start_local_server()`.

That creates:
- a `ChessTCPServer`
- a background thread that calls `serve_forever()`

So the server runs continuously while the main thread sleeps until interrupted.

### 5.2 What happens when a client connects
When a client connects:
- the server creates a `ChessRequestHandler`
- the handler stores a `ClientConnection` object
- the request handler loops reading lines from the socket
- each line is parsed as JSON into a `MessageEnvelope`
- the server logic dispatches the message based on its type

### 5.3 Connection state stored on the server
Each connected client has its own `ClientConnection` object.

That object stores:
- `socket`
- `address`
- `game_id`
- `color`
- a send lock

The send lock matters because socket writes can happen from different code paths.
It prevents message interleaving when sending from multiple threads.

### 5.4 Game session storage
The server keeps game state in memory using `ChessServerState.games`.

Each game session stores:
- `game_id`
- `board` (`shared.chess.Board`)
- `white` client connection
- `black` client connection

That means the server is the only source of truth for:
- the current board
- whose turn it is
- the legal state of the game

### 5.5 Create game flow
When the server receives `CreateGame`:
1. it generates a random short game id
2. it creates a new `GameSession`
3. it assigns the requesting client as white
4. it stores the session in memory
5. it sends `GameCreated` back to that client

The payload includes:
- the `game_id`
- the assigned color
- the current board text
- a waiting status

### 5.6 Join game flow
When the server receives `JoinGame`:
1. it looks up the session by `game_id`
2. it ensures the game exists
3. it ensures the game is not full
4. it assigns the joining client as black
5. it sends `GameStart` to both players

At this point both clients know:
- the same `game_id`
- their assigned colors
- the starting board state
- that the game is active

### 5.7 Move flow
When the server receives `MoveRequest`:
1. it verifies the `game_id`
2. it verifies the sender belongs to that game
3. it verifies the sender’s color matches `board.side_to_move`
4. it parses the UCI move string
5. it calls `board.push(move)`
6. if legal, it broadcasts `MoveAccepted`
7. if the game ended, it broadcasts `GameEnd`
8. if anything is invalid, it sends `MoveRejected`

This is the key rule:
- **the server decides whether a move is legal, not the client**

### 5.8 Disconnect flow
When a client disconnects:
- the server removes it from the session
- if the other player is still connected, the other player gets a `GameEnd`
- the session is cleaned up from memory if no players remain

This is a simple cleanup strategy for the current prototype.

---

## 6) Client-side connection flow

### 6.1 Client startup
`client/app.py` chooses one of two modes:
- console mode (`--ui console`, default)
- Qt mode (`--ui qt`)

Both modes use the same network client class:
- `LanChessClient`

### 6.2 Connection setup
`LanChessClient.connect()` does the following:
1. opens a TCP socket to the target host and port
2. sets a small socket timeout for the listener loop
3. starts a background listener thread
4. marks the client as connected

### 6.3 Listener thread
The background listener thread:
- reads bytes from the socket
- buffers partial reads
- splits on newline boundaries
- decodes each complete JSON line
- converts it into a `MessageEnvelope`
- places it onto a queue
- updates the local client state based on the message

This design is important because it means:
- the network can keep receiving messages while the UI is still active
- the main thread is not blocked by socket reads

### 6.4 Client-side state stored in memory
The client keeps track of:
- `game_id`
- `color`
- `board_text`
- `status`

This state is updated from server messages.
The server still remains authoritative.

### 6.5 Client send flow
To send a message:
1. create a `MessageEnvelope`
2. serialize it to JSON
3. append `\n`
4. send it with `socket.sendall(...)`

### 6.6 Client receive flow
When a message arrives, the client handles it by type:

- `GameCreated`
  - store the game id
  - store the assigned color
  - store the waiting board text

- `GameStart`
  - store the game id
  - store the assigned color
  - store the initial board text
  - mark the game as active

- `MoveAccepted`
  - update the board text
  - update the visible turn state

- `MoveRejected`
  - keep the board unchanged
  - show the reason

- `GameEnd`
  - update the final board text
  - mark the game as over

- `Error`
  - show the error text

### 6.7 Why the queue exists
The client has a `Queue[MessageEnvelope]` called `received`.

This queue lets the code do two things at once:
- keep track of the messages for testing or polling
- let the UI poll messages without blocking the socket thread

The Qt UI uses this queue to update the board on a timer.

---

## 7) How the Qt client fits into the connection model

The Qt client is just a visual front-end on top of the same socket connection.

Important points:
- Qt does **not** replace the connection model
- Qt only changes how the board is displayed and how the user inputs a move
- the actual network flow is still handled by `LanChessClient`

### 7.1 Visual board state
The Qt board widget does not talk to the server directly.
Instead it receives board text from `LanChessClient` and renders it.

### 7.2 Mouse interaction
The Qt board supports:
- click a piece, then click a target square
- drag a piece and release on a target square

When the user makes a move:
1. the board widget turns the mouse action into UCI like `e2e4`
2. it emits that move request
3. the window sends the request through `LanChessClient`
4. the server validates it
5. the server sends back the result
6. the board re-renders using the updated board text

### 7.3 Why this matters
This makes the UI and the networking layer separate:
- UI handles clicks and painting
- networking handles messages and server communication
- board logic remains server-authoritative

That separation is exactly what you want before moving the same logic to AWS.

---

## 8) Current chess-state synchronization model

The client does **not** maintain the authoritative board logic.
It only mirrors the server’s board text.

That means:
- the server applies the real move
- the server updates the board
- the server sends the new board text to both clients
- both clients repaint from the same source of truth

This avoids client/server drift.

### What the board text contains
The server sends a printable 8x8 board representation such as:

```text
8 r n b q k b n r
7 p p p p p p p p
6 . . . . . . . .
5 . . . . . . . .
4 . . . . . . . .
3 . . . . . . . .
2 P P P P P P P P
1 R N B Q K B N R
  a b c d e f g h
```

The client parses that text into a matrix for drawing.

---

## 9) What this connection model does well

This design is good for the current stage because it is:
- simple
- easy to debug
- human-readable
- good for local testing
- good for proving the full game loop early

It already supports:
- creating a game
- joining a game
- validating moves on the server
- sending board updates to both players
- showing the game visually in Qt

---

## 10) Current limitations

This model is still a prototype.
It does **not** yet include:

- TLS / encryption
- authentication
- reconnection/resync
- matchmaking queues
- invites
- multiple games simultaneously
- persistence/database storage
- WebSocket transport
- cloud deployment handling

Also, because it uses public TCP sockets directly, it can be blocked by:
- firewall rules
- client isolation on public Wi-Fi
- NAT/network restrictions

---

## 11) Why the model is still useful for the final project

Even though it is simple, the current connection model already captures the most important architectural idea:

> The server owns the truth, and clients are just views and input devices.

That pattern should remain the same when moving to AWS.

What is likely to change later:
- TCP line protocol may be replaced with WebSocket
- local server may become an AWS-hosted service
- the same JSON message shapes can still be reused

What should stay the same:
- authoritative server logic
- board state flow
- move validation on the server
- client rendering from server-approved state

---

## 12) Practical mental model

If you want to reason about the current connection quickly, think of it like this:

1. A client connects to a TCP port.
2. The client sends a JSON request line.
3. The server reads that line and updates game state.
4. The server sends JSON response lines back.
5. The client updates its local display from the server response.

Everything else is implementation detail around that loop.

---

## 13) Exact sequence for one game

### White creates game
1. White client connects.
2. White sends `CreateGame`.
3. Server creates a session and assigns white.
4. Server sends `GameCreated`.
5. White stores `game_id`.

### Black joins
1. Black client connects.
2. Black sends `JoinGame` with the same `game_id`.
3. Server assigns black.
4. Server sends `GameStart` to both.

### White moves
1. White sends `MoveRequest` with UCI like `e2e4`.
2. Server checks that it is white’s turn.
3. Server validates the move using the chess engine.
4. Server updates the board.
5. Server sends `MoveAccepted` to both.

### Black moves
Same process, but for black.

### Game ends
1. The chess engine detects checkmate or stalemate.
2. Server sends `GameEnd`.
3. Both clients mark the game as over.

---

## 14) Summary

The current connection is a **simple authoritative TCP game protocol**:

- TCP socket connection
- newline-delimited JSON messages
- server owns the board and move legality
- clients send requests and display server-approved state
- Qt is a visual layer on top of the same connection client

This is the exact baseline that will later be adapted to LAN, then AWS.

