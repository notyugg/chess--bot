import random

START_CASH = 1500
GO_SALARY = 200
JAIL_POS = 10
JAIL_FINE = 50
BOARD_SIZE = 40


def _prop(name, color, price):
    return {"type": "property", "name": name, "color": color, "price": price}


def _rail(name):
    return {"type": "railroad", "name": name, "price": 200}


def _util(name):
    return {"type": "utility", "name": name, "price": 150}


def _other(kind, name, amount=0):
    return {"type": kind, "name": name, "amount": amount}


BOARD = [
    _other("go", "GO"),
    _prop("Old Delhi", "brown", 60),
    _other("chance", "Chance"),
    _prop("Chandni Chowk", "brown", 60),
    _other("tax", "Income Tax", 200),
    _rail("Delhi Junction"),
    _prop("Kochi", "lightblue", 100),
    _other("chance", "Chance"),
    _prop("Goa", "lightblue", 100),
    _prop("Pune", "lightblue", 120),
    _other("jail", "Jail / Just Visiting"),
    _prop("Jaipur", "pink", 140),
    _util("Electric Company"),
    _prop("Udaipur", "pink", 140),
    _prop("Jodhpur", "pink", 160),
    _rail("Mumbai Central"),
    _prop("Lucknow", "orange", 180),
    _other("chance", "Chance"),
    _prop("Kanpur", "orange", 180),
    _prop("Varanasi", "orange", 200),
    _other("parking", "Free Parking"),
    _prop("Chennai", "red", 220),
    _other("chance", "Chance"),
    _prop("Hyderabad", "red", 220),
    _prop("Bengaluru", "red", 240),
    _rail("Howrah"),
    _prop("Kolkata", "yellow", 260),
    _prop("Ahmedabad", "yellow", 260),
    _util("Water Works"),
    _prop("Surat", "yellow", 280),
    _other("gotojail", "Go To Jail"),
    _prop("Chandigarh", "green", 300),
    _prop("Gurugram", "green", 300),
    _other("chance", "Chance"),
    _prop("Noida", "green", 320),
    _rail("Chennai Central"),
    _other("chance", "Chance"),
    _prop("Mumbai", "blue", 350),
    _other("tax", "Luxury Tax", 100),
    _prop("Delhi", "blue", 400),
]

CHANCE_CARDS = [
    ("Bank pays you a dividend of 50.", "collect", 50),
    ("You won a quiz competition. Collect 100.", "collect", 100),
    ("Pay a hospital bill of 100.", "pay", 100),
    ("Pay a speeding fine of 50.", "pay", 50),
    ("Advance to GO. Collect 200.", "move_to", 0),
    ("Take a trip to Delhi.", "move_to", 39),
    ("Go directly to Jail.", "gotojail", 0),
    ("Birthday! Collect 20 from every player.", "birthday", 20),
    ("Bank error in your favour. Collect 150.", "collect", 150),
    ("You receive a city development grant. Collect 100.", "collect", 100),
    ("Pay each opponent 50 for a neighbourhood celebration.", "per_player", 50),
    ("Unexpected legal fees. Pay 75.", "pay", 75),
]


def color_group(color):
    return [i for i, sq in enumerate(BOARD) if sq.get("color") == color]


class Player:
    def __init__(self, name):
        self.name = name
        self.cash = START_CASH
        self.position = 0
        self.in_jail = False
        self.jail_turns = 0
        self.properties = []
        self.bankrupt = False

    def to_dict(self):
        return {
            "name": self.name,
            "cash": self.cash,
            "position": self.position,
            "in_jail": self.in_jail,
            "properties": sorted(self.properties),
            "bankrupt": self.bankrupt,
            "net_worth": self.cash + sum(BOARD[i]["price"] for i in self.properties),
        }


class Game:

    def __init__(self, player_names):
        if not 2 <= len(player_names) <= 6:
            raise ValueError("Business needs 2 to 6 players")
        self.players = [Player(n) for n in player_names]
        self.owners = {}            # square index -> player index
        self.current = 0
        self.phase = "roll"
        self.last_roll = None
        self.rolled_doubles = False
        self.doubles_streak = 0
        self.log = []
        self.winner = None

    # Small helpers used by the game actions.
    @property
    def player(self):
        return self.players[self.current]

    def _log(self, msg):
        self.log.append(msg)
        self.log = self.log[-30:]

    def _check_phase(self, expected):
        if self.phase != expected:
            raise ValueError(f"Not allowed now (phase is '{self.phase}', need '{expected}')")

    def _move_to(self, pos, collect_go=True):
        p = self.player
        if collect_go and pos < p.position:
            p.cash += GO_SALARY
            self._log(f"{p.name} passed GO and collected {GO_SALARY}.")
        p.position = pos

    def _send_to_jail(self):
        p = self.player
        p.position = JAIL_POS
        p.in_jail = True
        p.jail_turns = 0
        self.rolled_doubles = False
        self.doubles_streak = 0
        self._log(f"{p.name} goes to Jail.")
        self.phase = "end_turn"

    def _pay(self, amount, to=None):
        p = self.player
        if p.cash >= amount:
            p.cash -= amount
            if to is not None:
                to.cash += amount
            return
        # Transfer any remaining properties when a player goes bankrupt.
        if to is not None:
            to.cash += p.cash
        p.cash = 0
        p.bankrupt = True
        creditor_idx = self.players.index(to) if to is not None else None
        for sq in p.properties:
            if creditor_idx is None:
                self.owners.pop(sq, None)
            else:
                self.owners[sq] = creditor_idx
                if sq not in to.properties:
                    to.properties.append(sq)
        p.properties = []
        self._log(f"{p.name} is bankrupt!")
        alive = [pl for pl in self.players if not pl.bankrupt]
        if len(alive) == 1:
            self.winner = alive[0].name
            self.phase = "over"
            self._log(f"{self.winner} wins the game!")

    def _land(self, dice_total):
        p = self.player
        sq = BOARD[p.position]
        kind = sq["type"]
        self.phase = "end_turn"

        if kind in ("property", "railroad", "utility"):
            idx = p.position
            if idx not in self.owners:
                if p.cash >= sq["price"]:
                    self.phase = "buy"
                    self._log(f"{p.name} landed on {sq['name']} (price {sq['price']}).")
                else:
                    self._log(f"{p.name} landed on {sq['name']} but cannot afford it.")
        elif kind == "tax":
            self._log(f"{p.name} pays {sq['name']} of {sq['amount']}.")
            self._pay(sq["amount"])
        elif kind == "gotojail":
            self._send_to_jail()
        elif kind == "chance":
            self._draw_chance(dice_total)

    def _draw_chance(self, dice_total):
        p = self.player
        text, action, value = random.choice(CHANCE_CARDS)
        self._log(f"Chance: {text}")
        if action == "collect":
            p.cash += value
        elif action == "pay":
            self._pay(value)
        elif action == "move_to":
            self._move_to(value)
            self._land(dice_total)
        elif action == "gotojail":
            self._send_to_jail()
        elif action == "birthday":
            for other in self.players:
                if other is not p and not other.bankrupt:
                    amt = min(value, other.cash)
                    other.cash -= amt
                    p.cash += amt
        elif action == "per_player":
            for other in self.players:
                if other is not p and not other.bankrupt and not p.bankrupt:
                    self._pay(value, other)

    def pay_jail_fine(self):
        """Optional: pay the fine at the start of your turn to leave jail."""
        self._check_phase("roll")
        p = self.player
        if not p.in_jail:
            raise ValueError("You are not in jail")
        if p.cash < JAIL_FINE:
            raise ValueError("Not enough cash for the fine")
        p.cash -= JAIL_FINE
        p.in_jail = False
        p.jail_turns = 0
        self._log(f"{p.name} paid {JAIL_FINE} and left Jail.")

    def roll(self):
        self._check_phase("roll")
        p = self.player
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2
        doubles = d1 == d2
        self.last_roll = [d1, d2]
        self._log(f"{p.name} rolled {d1} + {d2} = {total}.")

        if p.in_jail:
            if doubles:
                p.in_jail = False
                p.jail_turns = 0
                self._log(f"{p.name} rolled doubles and left Jail.")
            else:
                p.jail_turns += 1
                if p.jail_turns >= 3:
                    self._log(f"{p.name} pays {JAIL_FINE} after 3 turns in Jail.")
                    self._pay(JAIL_FINE)
                    if self.phase == "over":
                        return self.state()
                    p.in_jail = False
                    p.jail_turns = 0
                else:
                    self._log(f"{p.name} stays in Jail.")
                    self.phase = "end_turn"
                    self.rolled_doubles = False
                    return self.state()
            doubles = False              # no extra turn when leaving jail

        if doubles:
            self.doubles_streak += 1
            if self.doubles_streak == 3:
                self._log(f"{p.name} rolled 3 doubles in a row!")
                self._send_to_jail()
                return self.state()
        else:
            self.doubles_streak = 0
        self.rolled_doubles = doubles

        self._move_to((p.position + total) % BOARD_SIZE)
        self._land(total)
        return self.state()

    def buy(self):
        self._check_phase("buy")
        p = self.player
        sq = BOARD[p.position]
        p.cash -= sq["price"]
        p.properties.append(p.position)
        self.owners[p.position] = self.current
        self.phase = "end_turn"
        self._log(f"{p.name} bought {sq['name']} for {sq['price']}.")
        return self.state()

    def end_turn(self):
        self._check_phase("end_turn")
        if self.rolled_doubles and not self.player.bankrupt and not self.player.in_jail:
            self._log(f"{self.player.name} rolled doubles and goes again.")
            self.rolled_doubles = False
            self.phase = "roll"
            return self.state()
        self.doubles_streak = 0
        self.rolled_doubles = False
        while True:
            self.current = (self.current + 1) % len(self.players)
            if not self.player.bankrupt:
                break
        self.phase = "roll"
        self.last_roll = None
        return self.state()

    # Build the current game state for the frontend.

    def state(self):
        return {
            "players": [p.to_dict() for p in self.players],
            "current": self.current,
            "current_name": self.player.name,
            "phase": self.phase,
            "last_roll": self.last_roll,
            "owners": {str(k): v for k, v in self.owners.items()},
            "log": self.log[-10:],
            "winner": self.winner,
        }


def board_data():
    return BOARD


if __name__ == "__main__":
    g = Game(["Yug", "Friend"])
    for _ in range(300):
        if g.phase == "over":
            break
        if g.phase == "roll":
            g.roll()
        elif g.phase == "buy":
            g.buy()
        else:
            g.end_turn()
    for line in g.log:
        print(line)
    print(g.state()["players"])
    print("Winner:", g.winner)
    
    