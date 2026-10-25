"""Checkers (American/English draughts) rules engine.

Board: 8x8 list of lists. Pieces:
  'r' red man, 'R' red king   (human, moves UP the board, toward row 0)
  'b' black man, 'B' black king (bot, moves DOWN the board, toward row 7)
  '.' empty
Pieces live on dark squares only, i.e. where (row + col) % 2 == 1.

A move is a dict: {"path": [[r, c], ...], "captured": [[r, c], ...]}
 - path[0] is the starting square, path[-1] the landing square.
 - Multi-jumps have more than 2 squares in the path.
Rules implemented: forced capture, multi-jump, kings, a man that reaches the
far row mid-jump becomes a king and its turn ends.
"""

EMPTY = "."
RED, BLACK = "red", "black"


def initial_board():
    board = [[EMPTY] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            if (r + c) % 2 == 1:
                if r < 3:
                    board[r][c] = "b"
                elif r > 4:
                    board[r][c] = "r"
    return board


def owner(piece):
    if piece in ("r", "R"):
        return RED
    if piece in ("b", "B"):
        return BLACK
    return None


def opponent(player):
    return BLACK if player == RED else RED


def is_king(piece):
    return piece in ("R", "B")


def _directions(piece):
    if is_king(piece):
        return [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    return [(-1, -1), (-1, 1)] if owner(piece) == RED else [(1, -1), (1, 1)]


def _in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def _king_row(player):
    return 0 if player == RED else 7


def _jumps(board, r, c, piece, path, caps, out):
    """Depth-first search for all jump sequences from (r, c)."""
    me = owner(piece)
    found = False
    for dr, dc in _directions(piece):
        mr, mc = r + dr, c + dc          # square being jumped over
        lr, lc = r + 2 * dr, c + 2 * dc  # landing square
        if not _in_bounds(lr, lc):
            continue
        victim = board[mr][mc]
        if (
            victim != EMPTY
            and owner(victim) != me
            and (mr, mc) not in caps
            and board[lr][lc] == EMPTY
        ):
            found = True
            new_path = path + [(lr, lc)]
            new_caps = caps + [(mr, mc)]
            promotes = (not is_king(piece)) and lr == _king_row(me)
            if promotes:
                out.append((new_path, new_caps))  # turn ends on promotion
            else:
                _jumps(board, lr, lc, piece, new_path, new_caps, out)
    if not found and len(path) > 1:
        out.append((path, caps))


def get_moves(board, player):
    """All legal moves for `player`. If any capture exists, only captures."""
    captures, simple = [], []
    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if piece == EMPTY or owner(piece) != player:
                continue
            # --- captures (temporarily lift the piece so it can pass its origin)
            board[r][c] = EMPTY
            found = []
            _jumps(board, r, c, piece, [(r, c)], [], found)
            board[r][c] = piece
            for path, caps in found:
                captures.append(
                    {"path": [list(p) for p in path], "captured": [list(p) for p in caps]}
                )
            # --- simple moves
            for dr, dc in _directions(piece):
                nr, nc = r + dr, c + dc
                if _in_bounds(nr, nc) and board[nr][nc] == EMPTY:
                    simple.append({"path": [[r, c], [nr, nc]], "captured": []})
    return captures if captures else simple


def apply_move(board, move):
    """Return a NEW board with the move applied (input board is untouched)."""
    new = [row[:] for row in board]
    sr, sc = move["path"][0]
    er, ec = move["path"][-1]
    piece = new[sr][sc]
    new[sr][sc] = EMPTY
    for cr, cc in move["captured"]:
        new[cr][cc] = EMPTY
    if piece == "r" and er == 0:
        piece = "R"
    elif piece == "b" and er == 7:
        piece = "B"
    new[er][ec] = piece
    return new


def winner(board, player_to_move):
    """Return the winning colour, or None if the game continues.
    A player with no legal moves (no pieces or blocked) loses."""
    if not get_moves(board, player_to_move):
        return opponent(player_to_move)
    return None
