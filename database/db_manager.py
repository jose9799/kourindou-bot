"""Async data access layer.

Cogs never execute SQL: they call the domain functions exposed here. Anything that
moves faith is atomic and always writes an audit row into `transactions`.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

import config
from core.timeutils import utcnow_ts
from database.models import (
    DailyResult,
    InventoryEntry,
    ItemKind,
    LeaderboardEntry,
    PurchaseResult,
    Quote,
    ShopItem,
    Squad,
    SquadStatus,
    Transaction,
    TransferResult,
    TxReason,
    VoiceSession,
)

logger = logging.getLogger(__name__)


class _AbortError(Exception):
    """Rolls back the surrounding transaction and carries the result to report."""

    def __init__(self, result: object) -> None:
        super().__init__(str(result))
        self.result = result


class Database:
    def __init__(self, path: Path, schema_path: Path) -> None:
        self._path = path
        self._schema_path = schema_path
        self._conn: aiosqlite.Connection | None = None
        self._settings_cache: dict[int, dict[str, str]] = {}

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    # ------------------------------------------------------------------ lifecycle

    async def connect(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Autocommit mode: single statements commit on their own, and the explicit
        # BEGIN IMMEDIATE blocks below control their own transactions.
        self._conn = await aiosqlite.connect(self._path, isolation_level=None)
        self._conn.row_factory = aiosqlite.Row
        # SQLite ships with foreign keys disabled; this must run on every connection.
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.executescript(self._schema_path.read_text(encoding="utf-8"))
        logger.info("Database ready | path=%s", self._path)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            await self.conn.execute("ROLLBACK")
            raise
        else:
            await self.conn.execute("COMMIT")

    # ------------------------------------------------------------------- settings

    async def _overrides(self, guild_id: int) -> dict[str, str]:
        cached = self._settings_cache.get(guild_id)
        if cached is not None:
            return cached
        async with self.conn.execute(
            "SELECT key, value FROM guild_config WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        overrides = {row["key"]: row["value"] for row in rows}
        self._settings_cache[guild_id] = overrides
        return overrides

    async def get_setting(self, guild_id: int, key: str) -> int:
        """Return a numeric setting, falling back to the default in config.py."""
        default = config.SETTING_DEFAULTS[key]
        raw = (await self._overrides(guild_id)).get(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            logger.warning(
                "Invalid setting override, using default | guild=%s key=%s value=%r",
                guild_id,
                key,
                raw,
            )
            return default

    async def get_text_setting(self, guild_id: int, key: str, default: str = "") -> str:
        return (await self._overrides(guild_id)).get(key, default)

    async def set_setting(self, guild_id: int, key: str, value: str) -> None:
        await self.conn.execute(
            "INSERT INTO guild_config (guild_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT (guild_id, key) DO UPDATE SET value = excluded.value",
            (guild_id, key, value),
        )
        self._settings_cache.pop(guild_id, None)
        logger.info("Setting updated | guild=%s key=%s value=%r", guild_id, key, value)

    async def clear_setting(self, guild_id: int, key: str) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM guild_config WHERE guild_id = ? AND key = ?", (guild_id, key)
        )
        self._settings_cache.pop(guild_id, None)
        return cursor.rowcount > 0

    async def list_settings(self, guild_id: int) -> dict[str, str]:
        return dict(await self._overrides(guild_id))

    # ---------------------------------------------------------------------- users

    async def ensure_user(self, user_id: int, guild_id: int) -> None:
        await self.conn.execute(
            "INSERT OR IGNORE INTO users (user_id, guild_id, created_at) VALUES (?, ?, ?)",
            (user_id, guild_id, utcnow_ts()),
        )

    async def get_balance(self, user_id: int, guild_id: int) -> int:
        async with self.conn.execute(
            "SELECT faith_points FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row["faith_points"] if row else 0

    async def get_profile(self, user_id: int, guild_id: int) -> aiosqlite.Row | None:
        async with self.conn.execute(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
        ) as cursor:
            return await cursor.fetchone()

    async def _log_tx(
        self,
        guild_id: int,
        user_id: int,
        delta: int,
        reason: TxReason,
        counterparty: int | None = None,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO transactions (guild_id, user_id, delta, reason, counterparty, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, user_id, delta, reason.value, counterparty, utcnow_ts()),
        )

    async def add_faith(
        self,
        user_id: int,
        guild_id: int,
        amount: int,
        reason: TxReason,
        counterparty: int | None = None,
    ) -> int:
        """Credit faith unconditionally and return the resulting balance."""
        async with self._transaction():
            await self.ensure_user(user_id, guild_id)
            await self.conn.execute(
                "UPDATE users SET faith_points = faith_points + ? "
                "WHERE user_id = ? AND guild_id = ?",
                (amount, user_id, guild_id),
            )
            await self._log_tx(guild_id, user_id, amount, reason, counterparty)
        return await self.get_balance(user_id, guild_id)

    async def try_spend(
        self,
        user_id: int,
        guild_id: int,
        amount: int,
        reason: TxReason,
        counterparty: int | None = None,
    ) -> bool:
        """Debit faith only if the balance covers it. Returns False otherwise."""
        try:
            async with self._transaction():
                await self.ensure_user(user_id, guild_id)
                cursor = await self.conn.execute(
                    "UPDATE users SET faith_points = faith_points - ? "
                    "WHERE user_id = ? AND guild_id = ? AND faith_points >= ?",
                    (amount, user_id, guild_id, amount),
                )
                if cursor.rowcount == 0:
                    raise _AbortError(False)
                await self._log_tx(guild_id, user_id, -amount, reason, counterparty)
        except _AbortError:
            return False
        return True

    async def set_balance(self, user_id: int, guild_id: int, amount: int) -> int:
        async with self._transaction():
            await self.ensure_user(user_id, guild_id)
            current = await self.get_balance(user_id, guild_id)
            await self.conn.execute(
                "UPDATE users SET faith_points = ? WHERE user_id = ? AND guild_id = ?",
                (amount, user_id, guild_id),
            )
            await self._log_tx(guild_id, user_id, amount - current, TxReason.ADMIN)
        return amount

    # ---------------------------------------------------------------------- daily

    async def try_claim_daily(self, user_id: int, guild_id: int) -> DailyResult:
        """Grant the daily offering if the cooldown elapsed, applying the streak bonus."""
        cooldown = await self.get_setting(guild_id, "daily_cooldown_seconds")
        base = await self.get_setting(guild_id, "daily_base_reward")
        window = await self.get_setting(guild_id, "daily_streak_window_seconds")
        bonus_step = await self.get_setting(guild_id, "daily_streak_bonus_percent")
        bonus_cap = await self.get_setting(guild_id, "daily_streak_bonus_cap_percent")
        now = utcnow_ts()

        async with self._transaction():
            await self.ensure_user(user_id, guild_id)
            async with self.conn.execute(
                "SELECT faith_points, last_daily, daily_streak FROM users "
                "WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            ) as cursor:
                row = await cursor.fetchone()

            last_daily = row["last_daily"]
            elapsed = now - last_daily if last_daily else None
            if elapsed is not None and elapsed < cooldown:
                return DailyResult(
                    granted=False,
                    amount=0,
                    streak=row["daily_streak"],
                    bonus=0,
                    remaining_seconds=cooldown - elapsed,
                    new_balance=row["faith_points"],
                )

            streak = row["daily_streak"] + 1 if elapsed is not None and elapsed <= window else 1
            bonus_percent = min((streak - 1) * bonus_step, bonus_cap)
            bonus = base * bonus_percent // 100
            amount = base + bonus

            await self.conn.execute(
                "UPDATE users SET faith_points = faith_points + ?, last_daily = ?, "
                "daily_streak = ? WHERE user_id = ? AND guild_id = ?",
                (amount, now, streak, user_id, guild_id),
            )
            await self._log_tx(guild_id, user_id, amount, TxReason.DAILY)
            new_balance = row["faith_points"] + amount

        return DailyResult(
            granted=True,
            amount=amount,
            streak=streak,
            bonus=bonus,
            remaining_seconds=0,
            new_balance=new_balance,
        )

    # ------------------------------------------------------------------- transfer

    async def transfer_faith(
        self, sender_id: int, receiver_id: int, guild_id: int, amount: int
    ) -> tuple[TransferResult, int]:
        """Move faith between users atomically. Returns the result and the net amount."""
        fee_percent = await self.get_setting(guild_id, "transfer_fee_percent")
        min_age = await self.get_setting(guild_id, "transfer_min_account_age_seconds")
        fee = amount * fee_percent // 100
        net = amount - fee
        now = utcnow_ts()

        try:
            async with self._transaction():
                await self.ensure_user(sender_id, guild_id)
                await self.ensure_user(receiver_id, guild_id)

                async with self.conn.execute(
                    "SELECT created_at FROM users WHERE user_id = ? AND guild_id = ?",
                    (sender_id, guild_id),
                ) as cursor:
                    sender = await cursor.fetchone()
                if now - sender["created_at"] < min_age:
                    raise _AbortError(TransferResult.ACCOUNT_TOO_YOUNG)

                cursor = await self.conn.execute(
                    "UPDATE users SET faith_points = faith_points - ? "
                    "WHERE user_id = ? AND guild_id = ? AND faith_points >= ?",
                    (amount, sender_id, guild_id, amount),
                )
                if cursor.rowcount == 0:
                    raise _AbortError(TransferResult.INSUFFICIENT_FUNDS)

                await self.conn.execute(
                    "UPDATE users SET faith_points = faith_points + ? "
                    "WHERE user_id = ? AND guild_id = ?",
                    (net, receiver_id, guild_id),
                )
                await self._log_tx(guild_id, sender_id, -amount, TxReason.TRANSFER_OUT, receiver_id)
                await self._log_tx(guild_id, receiver_id, net, TxReason.TRANSFER_IN, sender_id)
                if fee:
                    await self._log_tx(guild_id, sender_id, -fee, TxReason.TRANSFER_FEE, None)
        except _AbortError as abort:
            return abort.result, 0

        logger.info(
            "Transfer completed | guild=%s from=%s to=%s amount=%s fee=%s",
            guild_id,
            sender_id,
            receiver_id,
            amount,
            fee,
        )
        return TransferResult.OK, net

    # ---------------------------------------------------------------- leaderboard

    async def get_leaderboard(self, guild_id: int, limit: int) -> list[LeaderboardEntry]:
        async with self.conn.execute(
            "SELECT user_id, faith_points FROM users WHERE guild_id = ? AND faith_points > 0 "
            "ORDER BY faith_points DESC, user_id ASC LIMIT ?",
            (guild_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            LeaderboardEntry(rank=index, user_id=row["user_id"], faith_points=row["faith_points"])
            for index, row in enumerate(rows, start=1)
        ]

    async def get_rank(self, user_id: int, guild_id: int) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) + 1 AS rank FROM users WHERE guild_id = ? AND faith_points > "
            "(SELECT faith_points FROM users WHERE user_id = ? AND guild_id = ?)",
            (guild_id, user_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row["rank"] if row else 0

    # ----------------------------------------------------------------- chat award

    async def try_award_chat(self, user_id: int, guild_id: int, amount: int, cooldown: int) -> bool:
        """Credit chat faith unless the user is still on cooldown."""
        now = utcnow_ts()
        try:
            async with self._transaction():
                await self.ensure_user(user_id, guild_id)
                cursor = await self.conn.execute(
                    "UPDATE users SET faith_points = faith_points + ?, last_message = ? "
                    "WHERE user_id = ? AND guild_id = ? "
                    "AND (last_message IS NULL OR last_message <= ?)",
                    (amount, now, user_id, guild_id, now - cooldown),
                )
                if cursor.rowcount == 0:
                    raise _AbortError(False)
                await self._log_tx(guild_id, user_id, amount, TxReason.CHAT)
        except _AbortError:
            return False
        return True

    # ------------------------------------------------------------------ voice

    async def open_voice_session(self, user_id: int, guild_id: int, channel_id: int) -> None:
        await self.conn.execute(
            "INSERT INTO voice_sessions (user_id, guild_id, channel_id, joined_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT (user_id, guild_id) DO UPDATE SET "
            "channel_id = excluded.channel_id",
            (user_id, guild_id, channel_id, utcnow_ts()),
        )

    async def close_voice_session(self, user_id: int, guild_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM voice_sessions WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
        )

    async def list_voice_sessions(self, guild_id: int) -> list[VoiceSession]:
        async with self.conn.execute(
            "SELECT * FROM voice_sessions WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            VoiceSession(
                user_id=row["user_id"],
                guild_id=row["guild_id"],
                channel_id=row["channel_id"],
                joined_at=row["joined_at"],
            )
            for row in rows
        ]

    async def consume_voice_minutes(self, user_id: int, guild_id: int) -> int:
        """Take the whole minutes accrued so far and advance the session clock.

        The remainder stays on the clock, so repeated settling never loses seconds.
        """
        now = utcnow_ts()
        async with self._transaction():
            async with self.conn.execute(
                "SELECT joined_at FROM voice_sessions WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id),
            ) as cursor:
                row = await cursor.fetchone()
            if row is None:
                return 0
            minutes = (now - row["joined_at"]) // 60
            if minutes <= 0:
                return 0
            await self.conn.execute(
                "UPDATE voice_sessions SET joined_at = joined_at + ? "
                "WHERE user_id = ? AND guild_id = ?",
                (minutes * 60, user_id, guild_id),
            )
        return int(minutes)

    async def award_voice(self, user_id: int, guild_id: int, minutes: int, amount: int) -> None:
        async with self._transaction():
            await self.ensure_user(user_id, guild_id)
            await self.conn.execute(
                "UPDATE users SET faith_points = faith_points + ?, voice_minutes = "
                "voice_minutes + ? WHERE user_id = ? AND guild_id = ?",
                (amount, minutes, user_id, guild_id),
            )
            await self._log_tx(guild_id, user_id, amount, TxReason.VOICE)

    # ------------------------------------------------------------------- shop

    @staticmethod
    def _row_to_item(row: aiosqlite.Row) -> ShopItem:
        return ShopItem(
            item_id=row["item_id"],
            guild_id=row["guild_id"],
            name=row["name"],
            description=row["description"],
            price=row["price"],
            kind=row["kind"],
            payload=row["payload"],
            stock=row["stock"],
            unique_owned=bool(row["unique_owned"]),
            enabled=bool(row["enabled"]),
        )

    async def list_shop_items(
        self, guild_id: int, include_disabled: bool = False
    ) -> list[ShopItem]:
        query = "SELECT * FROM shop_items WHERE guild_id = ?"
        if not include_disabled:
            query += " AND enabled = 1"
        query += " ORDER BY price ASC, name ASC"
        async with self.conn.execute(query, (guild_id,)) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_item(row) for row in rows]

    async def get_shop_item(self, item_id: int) -> ShopItem | None:
        async with self.conn.execute(
            "SELECT * FROM shop_items WHERE item_id = ?", (item_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_item(row) if row else None

    async def create_shop_item(
        self,
        guild_id: int,
        name: str,
        price: int,
        kind: ItemKind,
        description: str | None = None,
        payload: str | None = None,
        stock: int | None = None,
        unique_owned: bool = True,
    ) -> int | None:
        """Create a catalogue entry. Returns None when the name is already taken."""
        try:
            cursor = await self.conn.execute(
                "INSERT INTO shop_items (guild_id, name, description, price, kind, payload, "
                "stock, unique_owned) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    guild_id,
                    name,
                    description,
                    price,
                    kind.value,
                    payload,
                    stock,
                    int(unique_owned),
                ),
            )
        except aiosqlite.IntegrityError:
            return None
        return cursor.lastrowid

    async def delete_shop_item(self, item_id: int, guild_id: int) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM shop_items WHERE item_id = ? AND guild_id = ?", (item_id, guild_id)
        )
        return cursor.rowcount > 0

    async def set_item_enabled(self, item_id: int, guild_id: int, enabled: bool) -> bool:
        cursor = await self.conn.execute(
            "UPDATE shop_items SET enabled = ? WHERE item_id = ? AND guild_id = ?",
            (int(enabled), item_id, guild_id),
        )
        return cursor.rowcount > 0

    async def owns_item(self, user_id: int, guild_id: int, item_id: int) -> bool:
        async with self.conn.execute(
            "SELECT 1 FROM inventory WHERE user_id = ? AND guild_id = ? AND item_id = ?",
            (user_id, guild_id, item_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def purchase_item(self, user_id: int, guild_id: int, item: ShopItem) -> PurchaseResult:
        """Charge the user and register the item in a single transaction."""
        try:
            async with self._transaction():
                await self.ensure_user(user_id, guild_id)
                if not item.enabled:
                    raise _AbortError(PurchaseResult.UNAVAILABLE)

                if item.unique_owned:
                    async with self.conn.execute(
                        "SELECT 1 FROM inventory WHERE user_id = ? AND guild_id = ? "
                        "AND item_id = ?",
                        (user_id, guild_id, item.item_id),
                    ) as cursor:
                        if await cursor.fetchone():
                            raise _AbortError(PurchaseResult.ALREADY_OWNED)

                cursor = await self.conn.execute(
                    "UPDATE users SET faith_points = faith_points - ? "
                    "WHERE user_id = ? AND guild_id = ? AND faith_points >= ?",
                    (item.price, user_id, guild_id, item.price),
                )
                if cursor.rowcount == 0:
                    raise _AbortError(PurchaseResult.INSUFFICIENT_FUNDS)

                if item.stock is not None:
                    cursor = await self.conn.execute(
                        "UPDATE shop_items SET stock = stock - 1 WHERE item_id = ? AND stock > 0",
                        (item.item_id,),
                    )
                    if cursor.rowcount == 0:
                        raise _AbortError(PurchaseResult.OUT_OF_STOCK)

                await self.conn.execute(
                    "INSERT INTO inventory (user_id, guild_id, item_id, acquired_at) "
                    "VALUES (?, ?, ?, ?)",
                    (user_id, guild_id, item.item_id, utcnow_ts()),
                )
                await self._log_tx(guild_id, user_id, -item.price, TxReason.PURCHASE)
        except _AbortError as abort:
            return abort.result

        logger.info(
            "Purchase completed | guild=%s user=%s item=%s price=%s",
            guild_id,
            user_id,
            item.item_id,
            item.price,
        )
        return PurchaseResult.OK

    async def refund_purchase(self, user_id: int, guild_id: int, item: ShopItem) -> None:
        """Undo a purchase whose side effect failed outside the database."""
        async with self._transaction():
            await self.conn.execute(
                "DELETE FROM inventory WHERE entry_id = (SELECT entry_id FROM inventory "
                "WHERE user_id = ? AND guild_id = ? AND item_id = ? "
                "ORDER BY acquired_at DESC LIMIT 1)",
                (user_id, guild_id, item.item_id),
            )
            await self.conn.execute(
                "UPDATE users SET faith_points = faith_points + ? "
                "WHERE user_id = ? AND guild_id = ?",
                (item.price, user_id, guild_id),
            )
            if item.stock is not None:
                await self.conn.execute(
                    "UPDATE shop_items SET stock = stock + 1 WHERE item_id = ?", (item.item_id,)
                )
            await self._log_tx(guild_id, user_id, item.price, TxReason.REFUND)
        logger.warning(
            "Purchase refunded | guild=%s user=%s item=%s", guild_id, user_id, item.item_id
        )

    async def get_inventory(self, user_id: int, guild_id: int) -> list[InventoryEntry]:
        async with self.conn.execute(
            "SELECT i.entry_id, i.item_id, i.acquired_at, s.name, s.kind FROM inventory i "
            "JOIN shop_items s ON s.item_id = i.item_id "
            "WHERE i.user_id = ? AND i.guild_id = ? ORDER BY i.acquired_at DESC",
            (user_id, guild_id),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            InventoryEntry(
                entry_id=row["entry_id"],
                item_id=row["item_id"],
                name=row["name"],
                kind=row["kind"],
                acquired_at=row["acquired_at"],
            )
            for row in rows
        ]

    # ----------------------------------------------------------------- quotes

    async def add_quote(
        self,
        guild_id: int,
        author_id: int,
        added_by: int,
        content: str,
        message_link: str | None = None,
    ) -> int:
        cursor = await self.conn.execute(
            "INSERT INTO quotes (guild_id, author_id, added_by, content, message_link, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (guild_id, author_id, added_by, content, message_link, utcnow_ts()),
        )
        return cursor.lastrowid or 0

    @staticmethod
    def _row_to_quote(row: aiosqlite.Row) -> Quote:
        return Quote(
            quote_id=row["quote_id"],
            author_id=row["author_id"],
            added_by=row["added_by"],
            content=row["content"],
            message_link=row["message_link"],
            created_at=row["created_at"],
        )

    async def random_quote(self, guild_id: int, author_id: int | None = None) -> Quote | None:
        query = "SELECT * FROM quotes WHERE guild_id = ?"
        params: list[int] = [guild_id]
        if author_id is not None:
            query += " AND author_id = ?"
            params.append(author_id)
        query += " ORDER BY RANDOM() LIMIT 1"
        async with self.conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
        return self._row_to_quote(row) if row else None

    async def list_quotes(
        self, guild_id: int, author_id: int | None = None, limit: int = 50
    ) -> list[Quote]:
        query = "SELECT * FROM quotes WHERE guild_id = ?"
        params: list[int] = [guild_id]
        if author_id is not None:
            query += " AND author_id = ?"
            params.append(author_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_quote(row) for row in rows]

    async def delete_quote(self, quote_id: int, guild_id: int) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM quotes WHERE quote_id = ? AND guild_id = ?", (quote_id, guild_id)
        )
        return cursor.rowcount > 0

    # ----------------------------------------------------------------- squads

    async def create_squad(
        self,
        message_id: int,
        guild_id: int,
        channel_id: int,
        host_id: int,
        game: str,
        scheduled_at: str | None,
    ) -> None:
        await self.conn.execute(
            "INSERT INTO squads (message_id, guild_id, channel_id, host_id, game, "
            "scheduled_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (message_id, guild_id, channel_id, host_id, game, scheduled_at, utcnow_ts()),
        )

    async def get_squad(self, message_id: int) -> Squad | None:
        async with self.conn.execute(
            "SELECT * FROM squads WHERE message_id = ?", (message_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return Squad(
            message_id=row["message_id"],
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            host_id=row["host_id"],
            game=row["game"],
            scheduled_at=row["scheduled_at"],
            created_at=row["created_at"],
            closed=bool(row["closed"]),
        )

    async def set_squad_signup(self, message_id: int, user_id: int, status: SquadStatus) -> None:
        await self.conn.execute(
            "INSERT INTO squad_signups (message_id, user_id, status, updated_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT (message_id, user_id) DO UPDATE SET "
            "status = excluded.status, updated_at = excluded.updated_at",
            (message_id, user_id, status.value, utcnow_ts()),
        )

    async def get_squad_signups(self, message_id: int) -> dict[str, list[int]]:
        async with self.conn.execute(
            "SELECT user_id, status FROM squad_signups WHERE message_id = ? ORDER BY updated_at",
            (message_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        grouped: dict[str, list[int]] = {status.value: [] for status in SquadStatus}
        for row in rows:
            grouped.setdefault(row["status"], []).append(row["user_id"])
        return grouped

    async def close_squad(self, message_id: int) -> None:
        await self.conn.execute("UPDATE squads SET closed = 1 WHERE message_id = ?", (message_id,))

    async def list_open_squads(self) -> list[int]:
        async with self.conn.execute("SELECT message_id FROM squads WHERE closed = 0") as cursor:
            rows = await cursor.fetchall()
        return [row["message_id"] for row in rows]

    async def expire_squads(self, older_than: int) -> list[int]:
        async with self.conn.execute(
            "SELECT message_id FROM squads WHERE closed = 0 AND created_at < ?", (older_than,)
        ) as cursor:
            rows = await cursor.fetchall()
        expired = [row["message_id"] for row in rows]
        if expired:
            await self.conn.execute(
                "UPDATE squads SET closed = 1 WHERE closed = 0 AND created_at < ?", (older_than,)
            )
        return expired

    # ----------------------------------------------------------------- audit

    async def get_transactions(
        self, user_id: int, guild_id: int, limit: int = 15
    ) -> list[Transaction]:
        async with self.conn.execute(
            "SELECT delta, reason, counterparty, created_at FROM transactions "
            "WHERE user_id = ? AND guild_id = ? ORDER BY created_at DESC, tx_id DESC LIMIT ?",
            (user_id, guild_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            Transaction(
                delta=row["delta"],
                reason=row["reason"],
                counterparty=row["counterparty"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
