"""
business.py - backend logic for a Monopoly-style game ("Business").

Pure Python, no Flask in here. The Game class holds all state and exposes
methods (roll, buy, skip_buy, end_turn, pay_jail_fine) plus state() which
returns a JSON-friendly dict, so a Flask route can just do jsonify(game.state()).
"""
import random

START_CASH = 1500
GO_SALARY = 200
JAIL_POS = 10
JAIL_FINE = 50
BOARD_SIZE = 40
LOAN_STEP = 200
LOAN_LIMIT = 1000
LOAN_INTEREST_RATE = 0.10
BUILD_COST = {"brown": 50, "lightblue": 50, "pink": 100, "orange": 100, "red": 150, "yellow": 150, "green": 200, "blue": 200}


# ---------------------------------------------------------------- board ----
def _prop(name, color, price, rent):
    return {"type": "property", "name": name, "color": color, "price": price, "rent": rent}


def _rail(name):
    return {"type": "railroad", "name": name, "price": 200}


def _util(name):
    return {"type": "utility", "name": name, "price": 150}


def _other(kind, name, amount=0):
    return {"type": kind, "name": name, "amount": amount}


BOARD = [
    _other("go", "GO"),                                  # 0
    _prop("Old Delhi", "brown", 60, 4),                  # 1
    _other("chance", "Chance"),                          # 2
    _prop("Chandni Chowk", "brown", 60, 8),              # 3
    _other("tax", "Income Tax", 200),                    # 4
    _rail("Delhi Junction"),                             # 5
    _prop("Kochi", "lightblue", 100, 6),                 # 6
    _other("chance", "Chance"),                          # 7
    _prop("Goa", "lightblue", 100, 6),                   # 8
    _prop("Pune", "lightblue", 120, 8),                  # 9
    _other("jail", "Jail / Just Visiting"),              # 10
    _prop("Jaipur", "pink", 140, 10),                    # 11
    _util("Electric Company"),                           # 12
    _prop("Udaipur", "pink", 140, 10),                   # 13
    _prop("Jodhpur", "pink", 160, 12),                   # 14
    _rail("Mumbai Central"),                             # 15
    _prop("Lucknow", "orange", 180, 14),                 # 16
    _other("chance", "Chance"),                          # 17
    _prop("Kanpur", "orange", 180, 14),                  # 18
    _prop("Varanasi", "orange", 200, 16),                # 19
    _other("parking", "Free Parking"),                   # 20
    _prop("Chennai", "red", 220, 18),                    # 21
    _other("chance", "Chance"),                          # 22
    _prop("Hyderabad", "red", 220, 18),                  # 23
    _prop("Bengaluru", "red", 240, 20),                  # 24
    _rail("Howrah"),                                     # 25
    _prop("Kolkata", "yellow", 260, 22),                 # 26
    _prop("Ahmedabad", "yellow", 260, 22),               # 27
    _util("Water Works"),                                # 28
    _prop("Surat", "yellow", 280, 24),                   # 29
    _other("gotojail", "Go To Jail"),                    # 30
    _prop("Chandigarh", "green", 300, 26),               # 31
    _prop("Gurugram", "green", 300, 26),                 # 32
    _other("chance", "Chance"),                          # 33
    _prop("Noida", "green", 320, 28),                    # 34
    _rail("Chennai Central"),                            # 35
    _other("chance", "Chance"),                          # 36
    _prop("Mumbai", "blue", 350, 35),                    # 37
    _other("tax", "Luxury Tax", 100),                    # 38
    _prop("Delhi", "blue", 400, 50),                     # 39
]

# (text, action, value)
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
    ("Pay 25 for each house and 100 for each hotel.", "repairs", 0),
    ("Pay each opponent 50 for a neighbourhood celebration.", "per_player", 50),
    ("Collect 25 for each house and 100 for each hotel you own.", "building_income", 0),
    ("Unexpected legal fees. Pay 75.", "pay", 75),
]


def color_group(color):
    """Indexes of all properties of a colour."""
    return [i for i, sq in enumerate(BOARD) if sq.get("color") == color]


# --------------------------------------------------------------- player ----
class Player:
    def __init__(self, name):
        self.name = name
        self.cash = START_CASH
        self.position = 0
        self.in_jail = False
        self.jail_turns = 0
        self.properties = []
        self.bankrupt = False
        self.loan = 0
        self.mortgaged = []
        self.buildings = {}

    def to_dict(self):
        return {
            "name": self.name,
            "cash": self.cash,
            "position": self.position,
            "in_jail": self.in_jail,
            "properties": sorted(self.properties),
            "bankrupt": self.bankrupt,
            "loan": self.loan,
            "mortgaged": sorted(self.mortgaged),
            "buildings": {str(k): v for k, v in self.buildings.items()},
            "net_worth": self.cash + sum(BOARD[i]["price"] // 2 for i in self.properties) + sum(BUILD_COST.get(BOARD[i].get("color"), 50) * n // 2 for i, n in self.buildings.items()) - self.loan,
        }


# ----------------------------------------------------------------- game ----
class Game:
    """
    phase:
      "roll"     - current player must roll
      "buy"      - current player landed on an unowned square (buy or skip)
      "end_turn" - nothing left to do, call end_turn()
      "over"     - game finished, see winner
    """

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
        self.auction = None

    # ---- helpers ----
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
        """Player pays `amount` to another player (or the bank if to is None)."""
        p = self.player
        if p.cash >= amount:
            p.cash -= amount
            if to is not None:
                to.cash += amount
            return
        # cannot pay -> bankrupt: creditor gets everything the player has
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
                if sq not in to.properties: to.properties.append(sq)
        p.properties = []
        p.mortgaged = []
        p.buildings = {}
        p.loan = 0
        self._log(f"{p.name} is bankrupt!")
        alive = [pl for pl in self.players if not pl.bankrupt]
        if len(alive) == 1:
            self.winner = alive[0].name
            self.phase = "over"
            self._log(f"{self.winner} wins the game!")

    def _rent(self, sq_index, dice_total):
        sq = BOARD[sq_index]
        owner = self.players[self.owners[sq_index]]
        if sq_index in owner.mortgaged:
            return 0
        if sq["type"] == "property":
            houses = owner.buildings.get(sq_index, 0)
            if houses:
                return sq["rent"] * [1, 5, 15, 45, 80, 125][min(houses, 5)]
            rent = sq["rent"]
            group = color_group(sq["color"])
            if all(self.owners.get(i) == self.owners[sq_index] for i in group):
                rent *= 2                    # full colour set
            return rent
        if sq["type"] == "railroad":
            count = sum(1 for i in owner.properties if BOARD[i]["type"] == "railroad")
            return 25 * 2 ** (count - 1)
        # utility
        count = sum(1 for i in owner.properties if BOARD[i]["type"] == "utility")
        return dice_total * (10 if count == 2 else 4)

    # ---- landing logic ----
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
            elif self.owners[idx] != self.current:
                owner = self.players[self.owners[idx]]
                rent = self._rent(idx, dice_total)
                self._log(f"{p.name} pays {rent} rent to {owner.name} for {sq['name']}.")
                self._pay(rent, owner)
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
        elif action == "repairs":
            total = sum((100 if n == 5 else 25 * n) for n in p.buildings.values())
            self._log(f"{p.name} pays {total} in building repairs.")
            self._pay(total)
        elif action == "building_income":
            total = sum((100 if n == 5 else 25 * n) for n in p.buildings.values())
            p.cash += total
            self._log(f"{p.name} collects {total} from property improvements.")

    # ---- public actions (one per API route) ----
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

    def skip_buy(self):
        self._check_phase("buy")
        sq = BOARD[self.player.position]
        self._log(f"{self.player.name} passed on {sq['name']}; the property is up for auction.")
        self.auction = {"property": self.player.position, "bid": 0, "leader": None,
                        "passed": [], "turn": self.current, "eligible": [i for i, p in enumerate(self.players) if not p.bankrupt]}
        self.phase = "auction"
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
        if self.player.loan:
            interest = max(10, int(self.player.loan * LOAN_INTEREST_RATE + 0.5))
            self._log(f"{self.player.name} pays {interest} loan interest.")
            self._pay(interest)
            if self.phase == "over": return self.state()
        while True:
            self.current = (self.current + 1) % len(self.players)
            if not self.player.bankrupt:
                break
        self.phase = "roll"
        self.last_roll = None
        return self.state()

    # ---- serialisation ----

    def take_loan(self, amount=LOAN_STEP):
        self._check_phase("roll"); p = self.player
        try: amount = int(amount)
        except (TypeError, ValueError): raise ValueError("Loan amount must be a whole number.")
        if amount <= 0 or amount % LOAN_STEP: raise ValueError(f"Loans must be multiples of {LOAN_STEP}.")
        if p.loan + amount > LOAN_LIMIT: raise ValueError(f"Bank loan limit is {LOAN_LIMIT}.")
        p.loan += amount; p.cash += amount
        self._log(f"{p.name} borrowed {amount}; loan balance is {p.loan}.")
        return self.state()

    def repay_loan(self, amount=LOAN_STEP):
        self._check_phase("roll"); p = self.player
        try: amount = int(amount)
        except (TypeError, ValueError): raise ValueError("Repayment must be a whole number.")
        if amount <= 0 or amount % LOAN_STEP: raise ValueError(f"Repayments must be multiples of {LOAN_STEP}.")
        if p.loan <= 0: raise ValueError("You have no bank loan.")
        payment = min(amount, p.loan)
        if p.cash < payment: raise ValueError("Not enough cash to repay that amount.")
        p.cash -= payment; p.loan -= payment
        self._log(f"{p.name} repaid {payment}; loan balance is {p.loan}.")
        return self.state()

    def mortgage(self, square):
        self._check_phase("roll"); p = self.player
        try: square = int(square)
        except (TypeError, ValueError): raise ValueError("Choose a valid property.")
        if square not in p.properties: raise ValueError("You do not own that property.")
        if square in p.mortgaged: raise ValueError("That property is already mortgaged.")
        if p.buildings.get(square, 0): raise ValueError("Sell its buildings before mortgaging it.")
        sq = BOARD[square]
        if sq["type"] not in ("property", "railroad", "utility"): raise ValueError("That square cannot be mortgaged.")
        value = sq["price"] // 2; p.mortgaged.append(square); p.cash += value
        self._log(f"{p.name} mortgaged {sq['name']} for {value}.")
        return self.state()

    def unmortgage(self, square):
        self._check_phase("roll"); p = self.player
        try: square = int(square)
        except (TypeError, ValueError): raise ValueError("Choose a valid property.")
        if square not in p.properties or square not in p.mortgaged: raise ValueError("That property is not mortgaged by you.")
        cost = int(BOARD[square]["price"] * 0.55 + 0.5)
        if p.cash < cost: raise ValueError(f"You need {cost} to unmortgage it.")
        p.cash -= cost; p.mortgaged.remove(square)
        self._log(f"{p.name} unmortgaged {BOARD[square]['name']} for {cost}.")
        return self.state()


    def build(self, square):
        self._check_phase("roll"); p = self.player
        try: square = int(square)
        except (TypeError, ValueError): raise ValueError("Choose a valid property.")
        if square not in p.properties: raise ValueError("You do not own that property.")
        sq = BOARD[square]
        if sq.get("type") != "property" or square in p.mortgaged: raise ValueError("You cannot build there.")
        group = color_group(sq["color"])
        if not group or not all(self.owners.get(i) == self.current for i in group): raise ValueError("Own the full colour group to build.")
        if any(i in p.mortgaged for i in group): raise ValueError("Unmortgage the whole colour group first.")
        level = p.buildings.get(square, 0)
        if level >= 5: raise ValueError("This property already has a hotel.")
        if level > min(p.buildings.get(i, 0) for i in group): raise ValueError("Buildings must be spread evenly across the group.")
        cost = BUILD_COST[sq["color"]]
        if p.cash < cost: raise ValueError(f"You need {cost} to build.")
        p.cash -= cost; p.buildings[square] = level + 1
        self._log(f"{p.name} built a {'hotel' if level == 4 else 'house'} on {sq['name']} for {cost}.")
        return self.state()

    def sell_building(self, square):
        self._check_phase("roll"); p = self.player
        try: square = int(square)
        except (TypeError, ValueError): raise ValueError("Choose a valid property.")
        level = p.buildings.get(square, 0)
        if square not in p.properties or not level: raise ValueError("No building to sell there.")
        group = color_group(BOARD[square].get("color"))
        if level < max((p.buildings.get(i, 0) for i in group), default=0): raise ValueError("Sell buildings evenly across the group.")
        value = BUILD_COST[BOARD[square]["color"]] // 2
        p.cash += value
        if level == 1: p.buildings.pop(square, None)
        else: p.buildings[square] = level - 1
        self._log(f"{p.name} sold a building on {BOARD[square]['name']} for {value}.")
        return self.state()

    def trade(self, target, give_properties=None, take_properties=None, give_cash=0, take_cash=0):
        self._check_phase("roll")
        try:
            target=int(target); give_cash=int(give_cash); take_cash=int(take_cash)
            give_properties=[int(x) for x in (give_properties or [])]; take_properties=[int(x) for x in (take_properties or [])]
        except (TypeError, ValueError): raise ValueError("Trade details are invalid.")
        if target < 0 or target >= len(self.players) or target == self.current: raise ValueError("Choose another player.")
        p=self.player; other=self.players[target]
        if other.bankrupt: raise ValueError("That player is bankrupt.")
        if min(give_cash,take_cash) < 0: raise ValueError("Cash amounts cannot be negative.")
        if p.cash < give_cash or other.cash < take_cash: raise ValueError("A player cannot afford the cash part.")
        if any(i not in p.properties for i in give_properties): raise ValueError("You can only offer properties you own.")
        if any(i not in other.properties for i in take_properties): raise ValueError("You can only request properties they own.")
        if any(p.buildings.get(i,0) or other.buildings.get(i,0) for i in give_properties + take_properties): raise ValueError("Sell buildings before trading those properties.")
        for i in give_properties:
            p.properties.remove(i); other.properties.append(i); self.owners[i]=target
            if i in p.mortgaged: p.mortgaged.remove(i); other.mortgaged.append(i)
        for i in take_properties:
            other.properties.remove(i); p.properties.append(i); self.owners[i]=self.current
            if i in other.mortgaged: other.mortgaged.remove(i); p.mortgaged.append(i)
        p.cash += take_cash-give_cash; other.cash += give_cash-take_cash
        self._log(f"{p.name} completed a trade with {other.name}.")
        return self.state()


    def auction_bid(self, amount=10):
        if self.phase != "auction" or not self.auction: raise ValueError("No auction is active.")
        a=self.auction; p=self.player
        try: amount=int(amount)
        except (TypeError, ValueError): raise ValueError("Bid must be a whole number.")
        if amount < a["bid"]+10: raise ValueError(f"Bid at least {a['bid']+10}.")
        if p.bankrupt or p.cash < amount: raise ValueError("You cannot afford that bid.")
        a["bid"]=amount; a["leader"]=self.current; a["passed"]=[]
        self._log(f"{p.name} bids {amount} for {BOARD[a['property']]['name']}.")
        self._advance_auction(); return self.state()

    def auction_pass(self):
        if self.phase != "auction" or not self.auction: raise ValueError("No auction is active.")
        if self.current not in self.auction["passed"]: self.auction["passed"].append(self.current)
        self._log(f"{self.player.name} passes on the auction.")
        self._advance_auction(); return self.state()

    def _advance_auction(self):
        a=self.auction
        if not a: return
        eligible=[i for i in a["eligible"] if not self.players[i].bankrupt]
        leader=a["leader"]
        if leader is not None and all(i == leader or i in a["passed"] for i in eligible):
            sq=a["property"]; winner=self.players[leader]
            if winner.cash >= a["bid"]:
                winner.cash-=a["bid"]; winner.properties.append(sq); self.owners[sq]=leader
                self._log(f"{winner.name} won {BOARD[sq]['name']} at auction for {a['bid']}.")
            self.current=a["turn"]; self.auction=None; self.phase="end_turn"; return
        if leader is None and len(a["passed"]) >= len(eligible):
            self._log(f"No bids for {BOARD[a['property']]['name']}; it returns to the bank.")
            self.current=a["turn"]; self.auction=None; self.phase="end_turn"; return
        for step in range(1,len(self.players)+1):
            nxt=(self.current+step)%len(self.players)
            if nxt in eligible and nxt not in a["passed"]:
                self.current=nxt; return
        self.auction=None; self.phase="end_turn"

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
            "auction": self.auction,
            "finance": {"loan_step": LOAN_STEP, "loan_limit": LOAN_LIMIT, "interest_rate": LOAN_INTEREST_RATE, "building_costs": BUILD_COST},
            "board_assets": {str(i): {"mortgaged": i in self.players[o].mortgaged, "buildings": self.players[o].buildings.get(i, 0)} for i, o in self.owners.items()},
        }


def board_data():
    """Static board description for the frontend (send once)."""
    return BOARD


# ------------------------------------------------- quick terminal test ----
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
    
    