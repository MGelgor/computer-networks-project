# Online Chess Game (Python + Qt Client + AWS Server) -- Detailed Project Plan

## 0) Project goals & non-goals
### 0.1 Goals
- Build a desktop chess client in Python using Qt (PySide6 or PyQt6).
- Support online multiplayer through an AWS-hosted server.
- Server is authoritative: validates moves, enforces turns, and resolves game end conditions.

### 0.2 Non-goals (initially)
- No chess engine (no AI opponent) in v1.
- No tournaments/leaderboards in v1.
- No accounts/login system in v1.
- No persistence or game history in v1.
- No reconnect/resync in v1.
- No advanced UI features such as clocks, draw offers, resign buttons, or move lists.
- No packaging or installable `.app` in v1.

### 0.3 Acceptance criteria (v1)
- Two users can run the game locally on the same computer or on the same LAN, start a game, make legal moves, and finish a game.
- After the LAN/local version works, the same server/client flow can be switched to AWS hosting.
- Final AWS-hosted server is reachable over `wss://`.

---

## 1) High-level architecture
### 1.1 Components
- **Client (Qt desktop app)**
  - Renders board, handles user input, and sends move requests.
  - Displays the current board state received from the server.
- **Shared package**
  - Common types: enums, move objects, and protocol schema.
- **Server (FastAPI + WebSockets)**
  - Game session management.
  - Server-side move validation.
  - Runs locally first for LAN testing, then later on AWS.
- **Infrastructure (AWS)**
  - Final hosting target for the same server once local/LAN play is working.

### 1.2 Data flow (typical game)
1. Client opens a WebSocket connection to a locally running server on the same computer or LAN.
2. One client creates a game, the other joins it using a game code or ID.
3. Server creates a game session and sends `GameStart`.
4. Client makes a move locally in the UI and sends `MoveRequest`.
5. Server validates the move and broadcasts `MoveMade` to both players.
6. Server determines end conditions and sends `GameEnd`.
7. After the local/LAN flow is stable, the same flow is deployed to AWS with minimal changes.

---

## 2) Repository & workspace setup
### 2.1 Create repository layout
- Create folders:
  - `client/` -- Qt UI and app logic
  - `server/` -- FastAPI app, WebSockets, game logic
  - `shared/` -- shared chess rules + protocol types
  - `infra/` -- AWS deployment config
  - `tests/` -- unit/integration tests
- Add `.gitignore` for Python, PyCharm, and build artifacts.
- Add `README.md` with quick start commands.

### 2.2 Python tooling
- Choose Python version (3.11 or 3.12 recommended).
- Create `pyproject.toml` or a minimal dependency file with:
  - Testing: `pytest`
  - Client: Qt library (PySide6 or PyQt6)
  - Server: FastAPI, Uvicorn, WebSockets support
- Keep tooling minimal; do not add linting/type-checking setup unless needed later.

### 2.3 Run scripts (developer tasks)
- Create scripts:
  - `scripts/run_client.py` -- launches Qt client
  - `scripts/run_server_local.py` -- starts local server
- Keep only the scripts needed to start the app quickly.

Deliverable: repo boots locally with one command for server and one for client.

---

## 3) Shared domain model (rules + protocol)
### 3.1 Chess core types (`shared/chess/`)
Step breakdown:
1. **Enums**
   - `Color`: WHITE/BLACK
   - `PieceType`: KING/QUEEN/ROOK/BISHOP/KNIGHT/PAWN
   - `GameResult`: WHITE_WIN/BLACK_WIN/DRAW/ONGOING
2. **Square representation**
   - Internals: `(file, rank)` or 0-63 index
   - Conversion helpers:
     - `from_algebraic("e4") -> Square`
     - `to_algebraic() -> "e4"`
3. **Move object**
   - Fields: `from_sq`, `to_sq`, `promotion` (optional), flags (castle/en passant)
   - Serialize/deserialize to protocol format.
4. **Board state**
   - Piece placement
   - Side to move
   - Castling rights
   - En passant target (if any)
   - `from_fen()` and `to_fen()` for debugging
5. **Rules**
   - Legal move generation
   - Check detection
   - Special moves: castling, en passant, promotion
   - Endgame detection: checkmate/stalemate

Deliverable: shared chess rules validated by unit tests.

### 3.2 Message protocol (`shared/protocol/`)
Steps:
1. **Define message envelope**
   - Fields: `type`, `request_id` (optional), `payload`, `protocol_version`
2. **Define payload schemas**
   - Gameplay: `CreateGame`, `JoinGame`, `MoveRequest`, `GameStart`, `MoveMade`, `IllegalMove`, `GameEnd`
3. **Versioning**
   - `protocol_version` integer and compatibility checks.
4. **Serialization rules**
   - JSON only, no pickle.
   - Explicit field names and types.

Deliverable: protocol spec documented in `docs/protocol.md`.

### 3.3 Shared unit tests (`tests/shared/`)
- Test categories:
  - piece movement basics
  - check detection
  - castling legality
  - en passant correctness
  - promotion
  - common known positions (FEN fixtures)

Deliverable: `pytest` passes locally; rules correctness baseline.

---

## 4) Qt client application (`client/`)
### 4.1 UI structure (windows & widgets)
Steps:
1. **Main window**
   - Server URL field and Connect button
   - Create Game button
   - Join Game field + Join button
   - Status label for connection/game state
2. **Game view**
   - Board widget
   - No extra panels in v1

Deliverable: UI skeleton that runs and shows a placeholder board.

### 4.2 Board rendering & input
Steps:
1. Choose implementation:
   - `QWidget` custom paint, or
   - `QGraphicsView` scene with piece items
2. Rendering tasks:
   - draw 8x8 grid with coordinates
   - load piece images or simple text pieces
   - highlight selected square
3. Input tasks:
   - click-select + click-destination

Deliverable: local move selection updates UI state and emits a `move_attempted` signal.

### 4.3 Client state & controller layer
Steps:
1. Implement `GameController`
   - holds current board, game id, and player color
   - applies server moves to board
2. Implement `AppState`
   - connection state machine: DISCONNECTED/CONNECTED/IN_GAME
3. Signal/slot wiring
   - board widget emits `move_attempted(Move)`
   - controller sends to network layer
   - network layer emits server events
   - controller updates board and notifies UI

Deliverable: client UI updates from server events deterministically.

### 4.4 Networking (client)
Steps:
1. Use WebSocket for real-time game events.
2. Implement WebSocket client:
   - connect/disconnect
   - send JSON messages with envelope
   - receive loop integrated with Qt
3. Error handling:
   - show status bar errors
   - handle server `IllegalMove` by reverting local selection only

Deliverable: client can connect to local/AWS server and exchange messages.

---

## 5) Server application (`server/`)
### 5.1 Server skeleton
Steps:
1. FastAPI app with:
   - `/health` endpoint
   - `/ws` WebSocket endpoint
2. Configuration:
   - env vars for server host/port and game settings
   - dev defaults for local work
3. Logging:
   - structured logs to stdout

Deliverable: local server runs and responds to `/health`.

### 5.2 Game session management
Steps:
1. In-memory session store for active games
2. `GameSession` contents:
   - game id
   - player connections and assigned colors
   - current board
   - move list
3. `GameManager`
   - create game
   - join game
   - session cleanup on finish
4. Server-side move validation
   - uses `shared/chess` rules
   - verifies:
     - correct player turn
     - move exists in legal moves
     - game not ended

Deliverable: two clients can play a full game locally through the server.

### 5.3 Server tests
Steps:
1. Unit tests:
   - move validation edge cases
   - game start/join flow
2. Integration tests:
   - WS connect + play scripted sequence of moves

Deliverable: CI-ready test suite for server core behavior.

---

## 6) AWS infrastructure & deployment (`infra/`)
### 6.1 AWS account setup (user tasks)
Steps:
1. Create AWS account (or use existing).
2. Configure an AWS region for deployment.
3. Create the minimum access needed to deploy the server.

Deliverable: AWS account is ready for deployment.

### 6.2 Deployment target
Steps:
1. Take the working local/LAN server and move it to AWS with minimal code changes.
2. Choose one simple AWS compute target for the server.
3. Expose the server over TLS (`wss://`).
4. Point a domain or DNS name at the server endpoint.

Deliverable: the server is reachable from client machines over AWS.

### 6.3 Production verification checklist
- `/health` returns OK.
- WebSocket handshake succeeds over `wss://`.
- Two clients can play a complete game through the AWS-hosted server.

---

## 7) Security & reliability
### 7.1 Security baseline
- TLS everywhere (no plaintext WS).
- Server authoritative state only.
- Input validation on every message payload.

### 7.2 Reliability behaviors
- Keep the server session state in memory for the active game.
- Clean up finished or abandoned games.

Deliverable: stable two-player games with the minimum required protections.

---

## 8) End-user tasks (player workflow)
### 8.1 Play online
Steps:
1. Open the client.
2. Connect to the server.
3. Create or join a game.
4. Make moves on the board.
5. Finish the game.

### 8.2 After game
Steps:
1. View the final result.
2. Start a new game if desired.

---

## 9) Milestones & deliverables
### Milestone A: Chess core + local UI
- Board rendering
- Local move selection
- Rules + tests

### Milestone B: Local/LAN two-player play
- WebSocket protocol
- Local server on the same computer or LAN
- Two clients can create/join and play a full game

### Milestone C: Migrate to AWS hosting
- Deploy the same working server to AWS
- Expose the game over `wss://`
- Verify two clients can still play a full game

### Milestone D: Polish only if time remains
- Minor UI cleanup
- Better error messages
- Extra tests for edge cases
