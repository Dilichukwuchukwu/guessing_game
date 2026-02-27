# v0.1.0
# { "Depends": "py-genlayer:latest" }

from genlayer import *
from genlayer.gl.vm import UserError
from dataclasses import dataclass


@allow_storage
@dataclass
class GuessInfo:
    commitment: str
    stake: u256
    revealed: bool
    guess: str


class GuessingGame(gl.Contract):
    secret_commitment: str
    reveal_deadline: u256
    min_stake: u256
    guesses: TreeMap[Address, GuessInfo]
    balances: TreeMap[Address, u256]
    game_active: bool
    owner: Address

    def __init__(self):
        self.min_stake = u256(1)
        self.game_active = False
        self.owner = gl.message.sender_address

    # ------------------------------------------------
    # Owner starts a new game
    # secret_commitment = keccak256(secret + nonce)
    # ------------------------------------------------
    @gl.public.write
    def start_game(self, secret_commitment: str, reveal_window: int) -> None:
        if gl.message.sender_address != self.owner:
            raise UserError("not owner")
        if self.game_active:
            raise UserError("game already active")

        self.secret_commitment = secret_commitment
        self.reveal_deadline = u256(gl.block.timestamp) + reveal_window
        self.guesses.clear()
        self.game_active = True

    # ------------------------------------------------
    # Players commit their guess
    # guess_commitment = keccak256(guess + nonce)
    # ------------------------------------------------
    @gl.public.write
    def commit_guess(self, guess_commitment: str, stake: int) -> None:
        if not self.game_active:
            raise UserError("no active game")
        if stake < self.min_stake:
            raise UserError("stake too small")

        self.guesses[gl.message.sender_address] = GuessInfo(
            commitment=guess_commitment,
            stake=stake,
            revealed=False,
            guess="",
        )

    # ------------------------------------------------
    # Reveal guess
    # ------------------------------------------------
    @gl.public.write
    def reveal_guess(self, guess: str, nonce: str) -> None:
        if not self.game_active:
            raise UserError("no active game")

        sender = gl.message.sender_address
        if sender not in self.guesses:
            raise UserError("no guess committed")

        g = self.guesses[sender]
        if g.revealed:
            raise UserError("already revealed")

        expected = Keccak256((guess + nonce).encode()).hexdigest()
        if expected != g.commitment:
            raise UserError("commit mismatch")

        g.revealed = True
        g.guess = guess
        self.guesses[sender] = g

    # ------------------------------------------------
    # Owner reveals secret and resolves game
    # ------------------------------------------------
    @gl.public.write
    def reveal_secret(self, secret: str, nonce: str) -> None:
        if gl.message.sender_address != self.owner:
            raise UserError("not owner")
        if not self.game_active:
            raise UserError("no active game")
        if u256(gl.block.timestamp) < self.reveal_deadline:
            raise UserError("reveal too early")

        expected = Keccak256((secret + nonce).encode()).hexdigest()
        if expected != self.secret_commitment:
            raise UserError("invalid secret")

        winners: list[Address] = []
        total_pool = u256(0)

        for player, g in self.guesses.items():
            total_pool += g.stake
            if g.revealed and g.guess == secret:
                winners.append(player)

        if winners:
            reward = total_pool // u256(len(winners))
            for w in winners:
                self._credit(w, reward)

        self.game_active = False

    # ------------------------------------------------
    # Withdraw rewards
    # ------------------------------------------------
    @gl.public.write
    def withdraw(self) -> None:
        sender = gl.message.sender_address
        balance = self.balances.get(sender, u256(0))
        if balance == u256(0):
            raise UserError("nothing to withdraw")

        self.balances[sender] = u256(0)
        gl.transfer(sender, balance)

    # ------------------------------------------------
    # Internal balance helper
    # ------------------------------------------------
    def _credit(self, addr: Address, amount: int) -> None:
        current = self.balances.get(addr, u256(0))
        self.balances[addr] = current + amount

    # ------------------------------------------------
    # Optional parameter control
    # ------------------------------------------------
    @gl.public.write
    def set_min_stake(self, value: int) -> None:
        if gl.message.sender_address != self.owner:
            raise UserError("not owner")
        self.min_stake = value

# from genlayer import *

# class GuessingGame(gl.Contract):

#     def __init__(self):
#         self.state.secret_commitment = None
#         self.state.reveal_deadline = 0
#         self.state.min_stake = 1
#         self.state.guesses = {}
#         self.state.balances = {}
#         self.state.game_active = False
#         self.state.owner = caller()

#     # ------------------------------------------------
#     # Owner starts a new game
#     # secret_commitment = sha256(secret + nonce)
#     # ------------------------------------------------
#     @gl.public.view
#     def start_game(self, secret_commitment: str, reveal_window: int):

#         assert caller() == self.state.owner, "not owner"
#         assert not self.state.game_active, "game already active"

#         self.state.secret_commitment = secret_commitment
#         self.state.reveal_deadline = now() + reveal_window
#         self.state.guesses = {}
#         self.state.game_active = True

#     # ------------------------------------------------
#     # Players commit their guess
#     # guess_commitment = sha256(guess + nonce)
#     # ------------------------------------------------
#     @gl.public.view
#     def commit_guess(self, guess_commitment: str, stake: int):

#         assert self.state.game_active, "no active game"
#         assert stake >= self.state.min_stake, "stake too small"

#         self.state.guesses[caller()] = {
#             "commitment": guess_commitment,
#             "stake": stake,
#             "revealed": False,
#             "guess": None
#         }

#     # ------------------------------------------------
#     # Reveal guess
#     # ------------------------------------------------
#     @gl.public.view
#     def reveal_guess(self, guess: str, nonce: str):

#         assert self.state.game_active, "no active game"

#         g = self.state.guesses.get(caller())
#         assert g is not None, "no guess committed"
#         assert not g["revealed"], "already revealed"

#         expected = sha256(guess + nonce)
#         assert expected == g["commitment"], "commit mismatch"

#         g["revealed"] = True
#         g["guess"] = guess

#     # ------------------------------------------------
#     # Owner reveals secret and resolves game
#     # ------------------------------------------------
#     @gl.public.view
#     def reveal_secret(self, secret: str, nonce: str):

#         assert caller() == self.state.owner, "not owner"
#         assert self.state.game_active, "no active game"
#         assert now() >= self.state.reveal_deadline, "reveal too early"

#         expected = sha256(secret + nonce)
#         assert expected == self.state.secret_commitment, "invalid secret"

#         winners = []
#         total_pool = 0

#         for player, g in self.state.guesses.items():
#             total_pool += g["stake"]

#             if g["revealed"] and g["guess"] == secret:
#                 winners.append(player)

#         if winners:
#             reward = total_pool // len(winners)

#             for w in winners:
#                 self._credit(w, reward)

#         self.state.game_active = False

#     # ------------------------------------------------
#     # Withdraw rewards
#     # ------------------------------------------------
#     @gl.public.view
#     def withdraw(self):

#         balance = self.state.balances.get(caller(), 0)
#         assert balance > 0, "nothing to withdraw"

#         self.state.balances[caller()] = 0
#         transfer(caller(), balance)

#     # ------------------------------------------------
#     # Internal balance helper
#     # ------------------------------------------------
#     def _credit(self, addr, amount):
#         self.state.balances[addr] = self.state.balances.get(addr, 0) + amount

#     # ------------------------------------------------
#     # Optional parameter control
#     # ------------------------------------------------
#     @gl.public.view
#     def set_min_stake(self, value: int):
#         assert caller() == self.state.owner, "not owner"
#         self.state.min_stake = value
