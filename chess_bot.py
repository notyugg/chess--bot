"""
chess_bot.py - chess engine: minimax (negamax) with alpha-beta pruning, depth 3.

Needs:  pip install chess
Play in terminal:  py chess_bot.py
From Flask:        from chess_bot import best_move_uci   ->  best_move_uci(fen)
"""
import chess

DEPTH = 3
MATE = 100000

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Piece-square tables, written from White's point of view, rank 8 on top.
PST = {
    chess.PAWN: [
         0,  0,  0,  0,  0,  0,  0,  0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
         5,  5, 10, 25, 25, 10,  5,  5,
         0,  0,  0, 20, 20,  0,  0,  0,
         5, -5,-10,  0,  0,-10, -5,  5,
         5, 10, 10,-20,-20, 10, 10,  5,
         0,  0,  0,  0,  0,  0,  0,  0,
    ],
    chess.KNIGHT: [
       -50,-40,-30,-30,-30,-30,-40,-50,
       -40,-20,  0,  0,  0,  0,-20,-40,
       -30,  0, 10, 15, 15, 10,  0,-30,
       -30,  5, 15, 20, 20, 15,  5,-30,
       -30,  0, 15, 20, 20, 15,  0,-30,
       -30,  5, 10, 15, 15, 10,  5,-30,
       -40,-20,  0,  5,  5,  0,-20,-40,
       -50,-40,-30,-30,-30,-30,-40,-50,
    ],
    chess.BISHOP: [
       -20,-10,-10,-10,-10,-10,-10,-20,
       -10,  0,  0,  0,  0,  0,  0,-10,
       -10,  0,  5, 10, 10,  5,  0,-10,
       -10,  5,  5, 10, 10,  5,  5,-10,
       -10,  0, 10, 10, 10, 10,  0,-10,
       -10, 10, 10, 10, 10, 10, 10,-10,
       -10,  5,  0,  0,  0,  0,  5,-10,
       -20,-10,-10,-10,-10,-10,-10,-20,
    ],
    chess.ROOK: [
         0,  0,  0,  0,  0,  0,  0,  0,
         5, 10, 10, 10, 10, 10, 10,  5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
         0,  0,  0,  5,  5,  0,  0,  0,
    ],
    chess.QUEEN: [
       -20,-10,-10, -5, -5,-10,-10,-20,
       -10,  0,  0,  0,  0,  0,  0,-10,
       -10,  0,  5,  5,  5,  5,  0,-10,
        -5,  0,  5,  5,  5,  5,  0, -5,
         0,  0,  5,  5,  5,  5,  0, -5,
       -10,  5,  5,  5,  5,  5,  0,-10,
       -10,  0,  5,  0,  0,  0,  0,-10,
       -20,-10,-10, -5, -5,-10,-10,-20,
    ],
    chess.KING: [
       -30,-40,-40,-50,-50,-40,-40,-30,
       -30,-40,-40,-50,-50,-40,-40,-30,
       -30,-40,-40,-50,-50,-40,-40,-30,
       -30,-40,-40,-50,-50,-40,-40,-30,
       -20,-30,-30,-40,-40,-30,-30,-20,
       -10,-20,-20,-20,-20,-20,-20,-10,
        20, 20,  0,  0,  0,  0, 20, 20,
        20, 30, 10,  0,  0, 10, 30, 20,
    ],
}


def evaluate(board):
    """Score from the point of view of the side to move (positive = good for them)."""
    score = 0  # from White's point of view first
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        if piece.color == chess.WHITE:
            score += value + PST[piece.piece_type][chess.square_mirror(square)]
        else:
            score -= value + PST[piece.piece_type][square]
    return score if board.turn == chess.WHITE else -score


def order_moves(board):
    """Try captures (best victim, cheapest attacker) and promotions first - makes pruning much better."""
    def score(move):
        s = 0
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            if victim is None:               # en passant
                s += PIECE_VALUES[chess.PAWN] * 10
            else:
                s += 10 * PIECE_VALUES[victim.piece_type] - PIECE_VALUES[attacker.piece_type]
        if move.promotion:
            s += PIECE_VALUES[move.promotion]
        return s
    return sorted(board.legal_moves, key=score, reverse=True)


def negamax(board, depth, alpha, beta, ply):
    if board.is_checkmate():
        return -MATE + ply                   # being mated sooner is worse
    if board.is_game_over():
        return 0                             # stalemate / insufficient material / draw
    if depth == 0:
        return evaluate(board)

    best = -MATE
    for move in order_moves(board):
        board.push(move)
        score = -negamax(board, depth - 1, -beta, -alpha, ply + 1)
        board.pop()
        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:                    # alpha-beta cutoff
            break
    return best


def get_best_move(board, depth=DEPTH):
    """Return the best chess.Move for the side to move (or None if the game is over)."""
    best_move = None
    best_score = -MATE - 1
    alpha, beta = -MATE, MATE
    for move in order_moves(board):
        board.push(move)
        score = -negamax(board, depth - 1, -beta, -alpha, 1)
        board.pop()
        if score > best_score:
            best_score = score
            best_move = move
        if best_score > alpha:
            alpha = best_score
    return best_move


def best_move_uci(fen, depth=DEPTH):
    """Flask-friendly: FEN string in, move like 'e2e4' out (None if no moves)."""
    board = chess.Board(fen)
    move = get_best_move(board, depth)
    return move.uci() if move else None


# ------------------------------------------------------- play in terminal ----
def play_cli():
    board = chess.Board()
    print("You are White. Type moves like e2e4 (or SAN like Nf3). 'quit' to stop.\n")
    while not board.is_game_over():
        print(board, "\n")
        if board.turn == chess.WHITE:
            text = input("Your move: ").strip()
            if text == "quit":
                return
            try:
                try:
                    move = board.parse_uci(text)
                except ValueError:
                    move = board.parse_san(text)
            except ValueError:
                print("Illegal or unreadable move, try again.\n")
                continue
            board.push(move)
        else:
            move = get_best_move(board)
            print("Bot plays:", board.san(move), "\n")
            board.push(move)
    print(board, "\n")
    print("Game over:", board.result(), "-", board.outcome().termination.name)


if __name__ == "__main__":
    play_cli()