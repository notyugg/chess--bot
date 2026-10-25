"""Checkers bot: minimax with alpha-beta pruning."""
import math
from engine import (
    BLACK, RED, apply_move, get_moves, opponent, owner, is_king, winner,
)

WIN = 10_000


def evaluate(board):
    """Score from BLACK's (the bot's) point of view. Higher = better for bot."""
    score = 0
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == ".":
                continue
            value = 5 if is_king(p) else 3
            # men are worth more the closer they are to promotion
            if not is_king(p):
                advance = r if owner(p) == BLACK else 7 - r
                value += advance * 0.1
            # centre control bonus
            if 2 <= c <= 5 and 2 <= r <= 5:
                value += 0.2
            score += value if owner(p) == BLACK else -value
    return score


def minimax(board, depth, alpha, beta, player):
    result = winner(board, player)
    if result is not None:
        # prefer faster wins / slower losses
        return (WIN + depth) if result == BLACK else (-WIN - depth)
    if depth == 0:
        return evaluate(board)

    moves = get_moves(board, player)
    if player == BLACK:  # maximising
        best = -math.inf
        for m in moves:
            best = max(best, minimax(apply_move(board, m), depth - 1, alpha, beta, RED))
            alpha = max(alpha, best)
            if beta <= alpha:
                break
        return best
    best = math.inf  # minimising (human)
    for m in moves:
        best = min(best, minimax(apply_move(board, m), depth - 1, alpha, beta, BLACK))
        beta = min(beta, best)
        if beta <= alpha:
            break
    return best


def best_move(board, player=BLACK, depth=5):
    """Pick the best move for `player` (the bot is BLACK)."""
    moves = get_moves(board, player)
    if not moves:
        return None
    best, best_score = None, -math.inf if player == BLACK else math.inf
    for m in moves:
        score = minimax(apply_move(board, m), depth - 1, -math.inf, math.inf, opponent(player))
        if (player == BLACK and score > best_score) or (player == RED and score < best_score):
            best, best_score = m, score
    return best
