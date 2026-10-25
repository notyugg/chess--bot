# Game Hub (chess--bot)

A small Flask website with three games:

| Game | Files | How it works |
|------|-------|--------------|
| Chess | `chess_bot.py` | Minimax (negamax) with alpha-beta pruning, depth 3, using the `chess` library |
| Checkers | `engine.py`, `checkersbot.py` | Own rules engine (forced capture, multi-jump, kings) + minimax bot |
| Business | `business.py` | Monopoly-style game for 2 to 6 players |

## Run it

```
pip install -r requirements.txt
py app.py
```

Then open http://127.0.0.1:5000 (on Mac/Linux use `python3 app.py`).

## Project layout

```
app.py              Flask routes (pages + JSON API)
templates/          HTML pages (base, home, chess, checkers, business)
static/style.css    shared styling
```

## API (all JSON)

| Method | Route | What it does |
|--------|-------|--------------|
| POST | `/api/chess/move` | body `{fen, from, to}`: play your move, bot replies, returns new FEN |
| POST | `/api/chess/legal` | body `{fen, from}`: squares that piece can move to |
| GET | `/api/checkers/new` | fresh board + your legal moves |
| POST | `/api/checkers/move` | body `{board, move}`: play your move, bot replies |
| GET | `/api/business/board` | static board squares |
| POST | `/api/business/new` | body `{players: [names]}`: start a game |
| GET | `/api/business/state` | current game state |
| POST | `/api/business/roll` `buy` `skip` `end_turn` `pay_fine` | game actions |

## Team

Each person owns one game's file(s). Only edit your own game to avoid merge conflicts.
