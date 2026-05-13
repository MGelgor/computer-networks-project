# Computer Networks Project

This repository is being built in stages.

Current focus:
- chess pieces
- board state
- move generation
- turn logic
- core chess rules
- local/LAN connection flow
- AWS hosting later

## Run the current demo

```bash
python3 main.py
```

## Run the current scaffold entry points

```bash
python3 client/app.py
python3 server/app.py
python3 scripts/run_client.py
python3 scripts/run_server_local.py
```

## Run a local/LAN game

Open three terminals:

1. Start the server:

```bash
python3 scripts/run_server_local.py
```

2. Start the first client:

```bash
python3 scripts/run_client.py --name white
```

In the client, type:

```text
create
```

3. Start the second client in another terminal:

```bash
python3 scripts/run_client.py --name black
```

Join the game using the game id shown on the first client:

```text
join <game_id>
```

Then play moves like:

```text
move f2f3
move e7e5
move g2g4
move d8h4
```

## Run the tests

```bash
python3 scripts/run_tests.py
```

