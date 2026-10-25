"""Flask app: one site, three games (Chess, Checkers, Business).

Run:   py app.py        then open http://127.0.0.1:5000

How it is organised
  - Pages (GET)  : /, /chess, /checkers, /business  -> return HTML from templates/
  - API (JSON)   : /api/<game>/...                  -> the frontend calls these with fetch()
  - Game logic stays in its own file (chess_bot.py, engine.py + checkersbot.py, business.py).
    The routes here only translate HTTP <-> those functions.
"""
from flask import Flask, jsonify, render_template, request

import business
import checkersbot
import engine

app = Flask(__name__)


def error(message, code=400):
    """Every API error has the same JSON shape: {"error": "..."} + an HTTP status code."""
    return jsonify({"error": message}), code


# ------------------------------------------------------------------ pages ---
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chess")
def chess_page():
    return render_template("chess.html")


@app.route("/checkers")
def checkers_page():
    return render_template("checkers.html")


@app.route("/business")
def business_page():
    return render_template("business.html")


# ----------------------------------------------------------------- chess ----
# python-chess is imported lazily so the other games still work if it is missing.
@app.route("/api/chess/move", methods=["POST"])
def chess_move():
    """Body: {"fen": "...", "from": "e2", "to": "e4", "promotion": "q" (optional)}
    Plays the human move, then the bot replies. Returns the new FEN."""
    import chess
    import chess_bot

    data = request.get_json(silent=True) or {}
    try:
        board = chess.Board(data["fen"])
        uci = data["from"] + data["to"] + data.get("promotion", "")
        move = chess.Move.from_uci(uci)
    except (KeyError, ValueError):
        return error("Send JSON like {fen, from, to}.")

    if move not in board.legal_moves:
        return error("Illegal move.")
    board.push(move)

    bot_move = None
    if not board.is_game_over():
        bm = chess_bot.get_best_move(board)
        bot_move = bm.uci()
        board.push(bm)

    return jsonify({
        "fen": board.fen(),
        "bot_move": bot_move,
        "game_over": board.is_game_over(),
        "result": board.result() if board.is_game_over() else None,
        "in_check": board.is_check(),
    })


@app.route("/api/chess/legal", methods=["POST"])
def chess_legal():
    """Body: {"fen": "...", "from": "e2"} -> list of squares that piece can move to."""
    import chess

    data = request.get_json(silent=True) or {}
    try:
        board = chess.Board(data["fen"])
        src = chess.parse_square(data["from"])
    except (KeyError, ValueError):
        return error("Send JSON like {fen, from}.")
    targets = sorted({chess.square_name(m.to_square) for m in board.legal_moves if m.from_square == src})
    return jsonify({"targets": targets})


# -------------------------------------------------------------- checkers ----
# The client keeps the board and sends it each time (stateless server for this game).
CHECKERS_DEPTH = 4


@app.route("/api/checkers/new")
def checkers_new():
    board = engine.initial_board()
    return jsonify({"board": board, "moves": engine.get_moves(board, engine.RED)})


@app.route("/api/checkers/move", methods=["POST"])
def checkers_move():
    """Body: {"board": [[...]], "move": {"path": [...], "captured": [...]}}
    Checks the human (red) move is legal, applies it, then the bot (black) replies."""
    data = request.get_json(silent=True) or {}
    board, move = data.get("board"), data.get("move")
    if not board or not move:
        return error("Send JSON like {board, move}.")

    if move not in engine.get_moves(board, engine.RED):
        return error("Illegal move.")
    board = engine.apply_move(board, move)

    bot_move = None
    winner = engine.winner(board, engine.BLACK)  # black to move: can it move at all?
    if winner is None:
        bot_move = checkersbot.best_move(board, engine.BLACK, depth=CHECKERS_DEPTH)
        board = engine.apply_move(board, bot_move)
        winner = engine.winner(board, engine.RED)  # red to move: can it move at all?

    moves = [] if winner else engine.get_moves(board, engine.RED)
    return jsonify({"board": board, "bot_move": bot_move, "moves": moves, "winner": winner})


# -------------------------------------------------------------- business ----
# One shared game kept in memory on the server (fine for a demo: restarts reset it).
game = None


def need_game():
    return game is not None


@app.route("/api/business/board")
def business_board():
    return jsonify(business.board_data())


@app.route("/api/business/new", methods=["POST"])
def business_new():
    """Body: {"players": ["Yug", "Friend"]}"""
    global game
    data = request.get_json(silent=True) or {}
    names = [str(n).strip() for n in data.get("players", []) if str(n).strip()]
    try:
        game = business.Game(names)
    except ValueError as e:
        return error(str(e))
    return jsonify(game.state())


@app.route("/api/business/state")
def business_state():
    if not need_game():
        return error("No game yet. POST /api/business/new first.", 404)
    return jsonify(game.state())


def business_action(name):
    """Run a Game method (roll, buy, ...) and return the new state as JSON."""
    if not need_game():
        return error("No game yet. POST /api/business/new first.", 404)
    try:
        result = getattr(game, name)()
    except ValueError as e:        # the Game raises ValueError for illegal actions
        return error(str(e))
    return jsonify(result if result is not None else game.state())


@app.route("/api/business/roll", methods=["POST"])
def business_roll():
    return business_action("roll")


@app.route("/api/business/buy", methods=["POST"])
def business_buy():
    return business_action("buy")


@app.route("/api/business/skip", methods=["POST"])
def business_skip():
    return business_action("skip_buy")


@app.route("/api/business/end_turn", methods=["POST"])
def business_end_turn():
    return business_action("end_turn")


@app.route("/api/business/pay_fine", methods=["POST"])
def business_pay_fine():
    return business_action("pay_jail_fine")


if __name__ == "__main__":
    app.run(debug=True)
