# Chess Algorithm Development Steps

This document is the internal development guide for the chess logic and networking flow.

Use it as the order of implementation, not as a user-facing feature list.

The guiding principle is:
1. build the smallest correct board model,
2. make pieces move correctly,
3. enforce legal chess rules,
4. connect two clients over a local/LAN server,
5. then reuse the same server logic for AWS hosting.

Do not jump ahead unless the current step is already verified with tests.

---

## 1) Piece model

### 1.1 Define the data structures first
Create the minimal types needed to talk about chess pieces clearly.

Required enums:
- `Color`: `WHITE`, `BLACK`
- `PieceType`: `KING`, `QUEEN`, `ROOK`, `BISHOP`, `KNIGHT`, `PAWN`

Required piece fields:
- `color`
- `piece_type`

Optional later, only if needed by implementation:
- `has_moved`
- `symbol` or `unicode_symbol`

### 1.2 Decide how pieces will be represented
Pick one simple representation and keep it everywhere.

Recommended approach:
- a small piece object or dataclass
- no inheritance tree unless it clearly helps

The piece object should be lightweight, because most game logic will live in board/rules code rather than in piece methods.

### 1.3 Implement each piece’s movement pattern
Work through the pieces one by one.

For each piece, define:
- how it moves on an empty board
- how it captures
- what blocks its movement
- whether it has special rules

Piece-specific checklist:

- **Pawn**
  - moves one square forward
  - moves two squares forward from its starting rank
  - captures diagonally
  - promotes on the last rank
  - supports en passant later in the rules step

- **Knight**
  - moves in L-shapes
  - ignores blocking pieces between start and destination
  - can capture an enemy piece on the destination square

- **Rook**
  - moves horizontally and vertically
  - cannot jump over pieces
  - stops at the first blocking piece

- **Bishop**
  - moves diagonally
  - cannot jump over pieces
  - stops at the first blocking piece

- **Queen**
  - combines rook + bishop movement
  - cannot jump over pieces

- **King**
  - moves one square in any direction
  - must not move into check
  - handles castling in the rules step

### 1.4 Build the pieces in a safe order
Use this implementation order:
1. Pawn
2. Knight
3. Rook
4. Bishop
5. Queen
6. King

Why this order:
- pawns are easy to verify early
- knights are also simple because they do not slide
- rooks and bishops introduce blocking logic
- queen reuses earlier logic
- king depends on check detection and castling rules

### 1.5 Verify each piece before moving on
After each piece is implemented, test it on a simple board.

Check:
- legal moves are correct
- illegal moves are rejected
- captures work
- blocked movement works for sliding pieces

Do not move to the board/rules layer until basic piece movement is reliable.

---

## 2) Board model

### 2.1 Choose one board representation
Use a single board representation everywhere.

Recommended options:
- 8x8 grid
- 0-63 flat list

Choose the one that is easiest to debug and keep it consistent between:
- board logic
- move generation
- rendering
- networking state sync

### 2.2 Define the board state
The board must track all state required to make a move legally.

Required state:
- piece placement
- side to move
- castling rights
- en passant target square
- move history
- game result / game status

### 2.3 Create board constructors
Implement these constructors early:
- initial chess position
- empty board for unit tests
- clone/copy board for move simulation

The empty board is especially useful for testing one rule at a time without interference from other pieces.

### 2.4 Add board helper functions
The board layer should include simple utilities such as:
- convert algebraic notation to internal coordinates
- convert internal coordinates back to algebraic notation
- get piece at square
- set piece at square
- remove piece from square
- check whether a square is inside the board

Optional later:
- FEN export/import for debugging

### 2.5 Define board responsibilities clearly
The board should be responsible for:
- storing the current position
- applying a legal move
- updating turn state
- updating castling/en passant state
- returning the state needed for client rendering

The board should not yet worry about networking details.

### 2.6 Verify the board layer independently
Before adding full rules, test that the board:
- starts with the correct initial setup
- supports empty setup for tests
- can clone itself
- can place and remove pieces correctly

This avoids debugging move logic on top of a broken board model.

---

## 3) Move generation

### 3.1 Start with pseudo-legal moves
Generate pseudo-legal moves first.

Pseudo-legal means:
- the move follows the piece’s movement pattern
- the move may still be illegal because it leaves the king in check

This is the easiest way to get the engine working in stages.

### 3.2 Generate moves per piece type
For each piece on the board:
- inspect its movement pattern
- generate every reachable destination
- stop on blocked squares when the piece is a slider
- mark captures separately from quiet moves if useful

### 3.3 Define the move object
Each move should hold the minimum information needed to apply it and replay it.

Recommended fields:
- `from_square`
- `to_square`
- `promotion` if applicable
- castling flag if applicable
- en passant flag if applicable

Optional later:
- captured piece information
- move notation string

### 3.4 Filter pseudo-legal moves into legal moves
After generating candidate moves, filter out any move that leaves the moving side’s king in check.

That means the workflow becomes:
1. generate candidate move
2. apply it to a cloned board
3. check whether own king is attacked
4. keep it only if the board remains legal

### 3.5 Validation flow for a move attempt
Every move attempt should follow this order:
1. confirm the source square contains a piece
2. confirm the piece belongs to the current player
3. confirm the destination is in the legal move set
4. apply the move
5. update board state and turn state
6. evaluate game end conditions

### 3.6 Add movement tests before rules tests
Test generation on small boards first:
- one rook in the center
- one bishop in the center
- one knight in the center
- one pawn in each key starting scenario

That makes it much easier to catch move-generation bugs before adding check logic.

---

## 4) Turn logic

### 4.1 Make turn ownership explicit
The board must always know whose turn it is.

Use one field for it:
- `side_to_move`

This field should be checked before any move is accepted.

### 4.2 Enforce turn order at the server/game layer
When a client sends a move:
1. read the current `side_to_move`
2. compare it with the sender’s assigned color
3. reject the move if they do not match

Do not wait until after the move is applied to notice turn mismatch.

### 4.3 Switch turns only after a legal move
After a legal move:
- apply the board change
- update move history
- switch `side_to_move` to the opponent
- evaluate whether the game ended

### 4.4 Handle illegal moves cleanly
If the move is illegal:
- reject it immediately
- do not modify the board
- do not change the turn
- send an error response to the client

The client should never need to guess whether the server accepted the move.

### 4.5 Add special turn-related state changes
Some turn changes affect hidden board state.

Make sure you update:
- castling rights when a king or rook moves
- en passant target when a pawn moves two squares
- promotion when a pawn reaches the last rank

These changes must happen as part of the move application step, not as a separate afterthought.

### 4.6 Verify turn logic with simple scenarios
Test these cases explicitly:
- white moves first
- black cannot move twice in a row
- illegal move does not change the turn
- legal move flips the turn exactly once

---

## 5) Chess rules

### 5.1 Implement check detection first
Create a function such as:
- `is_in_check(board, color)`

This function should answer one question only:
- is the given color’s king currently attacked?

Keep it focused and test it independently.

### 5.2 Define attack detection carefully
Check detection needs a way to answer whether a square is attacked.

Implement attack logic by piece type:
- pawns attack diagonally
- knights attack in L-shapes
- rooks attack along ranks/files
- bishops attack diagonally
- queens attack like rook + bishop
- kings attack adjacent squares

This attack logic will also help later with castling and legal move filtering.

### 5.3 Implement checkmate detection
A side is checkmated only if:
- the king is in check
- no legal move can remove the check

That means checkmate depends on legal move generation, not just check detection alone.

### 5.4 Implement stalemate detection
A side is stalemated only if:
- the king is not in check
- no legal move exists

Do not treat stalemate as checkmate.

### 5.5 Add special move rules
Implement these chess rules in the rules layer:
- castling
- en passant
- pawn promotion

For each one, define:
- when it is allowed
- what board state it changes
- how it affects move generation
- how it affects move application

### 5.6 Keep optional rules separate
Optional later:
- threefold repetition
- 50-move rule

If the project timeline is tight, skip them at first and keep the rules engine focused on the essential chess mechanics.

### 5.7 Verify rules one rule at a time
Test each rule independently:
- check detection on simple attack positions
- castling on empty-path positions
- en passant on a controlled pawn sequence
- promotion on a pawn reaching the final rank
- checkmate and stalemate on known positions

---

## 6) Testing strategy

### 6.1 Piece tests
For each piece, test:
- movement on an empty board
- captures
- blocked movement for sliding pieces
- boundary behavior near board edges

For pawns, also test:
- first-move double advance
- diagonal capture
- promotion path

### 6.2 Board tests
Test the board layer itself:
- initial setup is correct
- empty board setup works
- cloning works and does not mutate the original
- applying a move changes the correct squares
- special state updates correctly

### 6.3 Rules tests
Test these rules explicitly:
- check detection
- checkmate
- stalemate
- castling legality
- en passant legality

### 6.4 Move-validation tests
Test the full move acceptance pipeline:
- moving from an empty square
- moving the wrong color
- moving to an illegal destination
- moving through pieces when not allowed
- moving into check

### 6.5 Regression tests
Whenever a bug is found:
1. write a failing test first
2. fix the code
3. re-run the test
4. keep the test forever

This is the main way to prevent chess-rule regressions.

---

## 7) Connection flow

### 7.1 Start locally or on LAN before AWS
Before any AWS deployment, make the system work in a local/LAN setup:
- one local server process
- two client instances
- clients connect over `ws://` on the same computer or LAN

This proves the chess logic and networking together.

### 7.2 Keep the protocol minimal
Use a small JSON protocol.

Required message types:
- `CreateGame`
- `JoinGame`
- `MoveRequest`
- `MoveAccepted`
- `MoveRejected`
- `GameStart`
- `GameEnd`

Keep the protocol simple enough that it is easy to debug with raw message logging.

### 7.3 Define connection responsibilities
The connection layer should:
- open and close WebSocket connections
- send JSON messages
- receive JSON messages
- route messages to the game logic
- update the client board from server-approved moves

The connection layer should not contain chess rules itself.

### 7.4 Server responsibilities in the connection flow
The server should:
- create a game
- allow a second player to join
- assign colors
- forward legal moves to both clients
- reject illegal moves
- send game-end notifications

### 7.5 AWS migration later
Once local/LAN play works:
- reuse the same server logic
- keep the protocol unchanged if possible
- change only the deployment target and server URL

The goal is for AWS to be a hosting change, not a redesign.

---

## 8) Recommended implementation order

Follow this order while developing:

1. Board representation
2. Piece data model
3. Pawn movement
4. Knight movement
5. Rook movement
6. Bishop movement
7. Queen movement
8. King movement
9. Basic move generation
10. Legal move filtering
11. Turn enforcement
12. Check detection
13. Checkmate and stalemate
14. Castling
15. En passant
16. Promotion
17. Move application and board state updates
18. Server message protocol
19. Local/LAN multiplayer tests
20. AWS deployment reuse

If a step fails, stop and fix it before continuing.

---

## 9) Definition of done

The chess algorithm work is complete when all of the following are true:
- every piece moves according to chess rules
- the board state updates correctly after every move
- turns alternate correctly
- illegal moves are rejected
- check, checkmate, and stalemate are handled correctly
- local/LAN multiplayer works through the server
- the same server/client logic can later be moved to AWS without redesign

At that point, the chess engine and connection flow are ready for the rest of the project.


