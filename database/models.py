"""Typed results returned by the database layer.

These cross the boundary between db_manager and the cogs, so they never contain
Discord objects nor raw sqlite rows.
"""

from dataclasses import dataclass
from enum import Enum


class TxReason(str, Enum):
    DAILY = "daily"
    CHAT = "chat"
    VOICE = "voice"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_FEE = "transfer_fee"
    PURCHASE = "purchase"
    REFUND = "refund"
    BET = "bet"
    PAYOUT = "payout"
    ADMIN = "admin"


class ItemKind(str, Enum):
    ROLE = "role"
    PERK = "perk"
    COSMETIC = "cosmetic"
    CONSUMABLE = "consumable"


class TransferResult(str, Enum):
    OK = "ok"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    ACCOUNT_TOO_YOUNG = "account_too_young"


class PurchaseResult(str, Enum):
    OK = "ok"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    ALREADY_OWNED = "already_owned"
    OUT_OF_STOCK = "out_of_stock"
    UNAVAILABLE = "unavailable"
    ROLE_FAILED = "role_failed"


class SquadStatus(str, Enum):
    IN = "in"
    LATE = "late"
    OUT = "out"


@dataclass(frozen=True, slots=True)
class DailyResult:
    granted: bool
    amount: int
    streak: int
    bonus: int
    remaining_seconds: int
    new_balance: int


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    rank: int
    user_id: int
    faith_points: int


@dataclass(frozen=True, slots=True)
class WalletProfile:
    user_id: int
    guild_id: int
    faith_points: int
    breakcoins: int
    rank: int
    voice_minutes: int
    daily_streak: int


@dataclass(frozen=True, slots=True)
class ShopItem:
    item_id: int
    guild_id: int
    name: str
    description: str | None
    price: int
    kind: str
    payload: str | None
    stock: int | None
    unique_owned: bool
    enabled: bool


@dataclass(frozen=True, slots=True)
class InventoryEntry:
    entry_id: int
    item_id: int
    name: str
    kind: str
    acquired_at: int


@dataclass(frozen=True, slots=True)
class Quote:
    quote_id: int
    author_id: int
    added_by: int
    content: str
    message_link: str | None
    created_at: int


@dataclass(frozen=True, slots=True)
class Transaction:
    delta: int
    reason: str
    counterparty: int | None
    currency: str
    created_at: int


@dataclass(frozen=True, slots=True)
class VoiceSession:
    user_id: int
    guild_id: int
    channel_id: int
    joined_at: int


@dataclass(frozen=True, slots=True)
class Squad:
    message_id: int
    guild_id: int
    channel_id: int
    host_id: int
    game: str
    scheduled_at: str | None
    created_at: int
    closed: bool
