"""Gambling minigames: coin duel, Nitori's slots and the Gensokyo roulette."""

import logging
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from discord.ext import commands

import config
import strings
from core import embeds
from core.text import fmt_number
from database.models import TxReason

if TYPE_CHECKING:
    from main import KourindouBot

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SlotSymbol:
    emoji: str
    weight: int
    triple_multiplier: int


# Reel table. Weights add up to 100, so each weight is a percentage.
#
# RTP derivation (three independent reels, p = weight / 100):
#   P(pair)   = sum over s of 3 * p^2 * (1 - p)          = 0.492006
#   P(triple) = sum over s of p^3                        = 0.053398
#   RTP = 1.0 * P(pair) + sum over s of p^3 * multiplier
#       = 0.492006 + 0.458125 = 0.950131  ->  95.01%
# A pair returns the stake, so the real cost of playing comes from the 45.5% of
# spins that match nothing. Changing any weight or multiplier invalidates this
# number: recompute it before shipping the change.
SLOT_SYMBOLS = (
    SlotSymbol("🌸", 30, 5),
    SlotSymbol("🍡", 25, 7),
    SlotSymbol("⛩️", 20, 12),
    SlotSymbol("🔴", 13, 30),
    SlotSymbol("🗡️", 8, 70),
    SlotSymbol("🌙", 4, 250),
)
PAIR_MULTIPLIER = 1

# European wheel: a single zero gives the house its 1/37 edge, so both bet types
# land on the same 97.3% RTP.
ROULETTE_SLOTS = 37
ROULETTE_RED = frozenset({1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36})
ROULETTE_COLOR_MULTIPLIER = 2
ROULETTE_RANGE_MULTIPLIER = 3
ROULETTE_RANGES = {"1-12": range(1, 13), "13-24": range(13, 25), "25-36": range(25, 37)}


class GamesCog(commands.Cog, name="Juegos"):
    def __init__(self, bot: "KourindouBot") -> None:
        self.bot = bot

    async def _take_bet(self, ctx: commands.Context, amount: int) -> bool:
        """Validate and charge the stake. False means the caller must stop."""
        assert ctx.guild is not None
        minimum = await self.bot.db.get_setting(ctx.guild.id, "bet_min")
        maximum = await self.bot.db.get_setting(ctx.guild.id, "bet_max")
        if not minimum <= amount <= maximum:
            await ctx.send(
                embed=embeds.error(
                    strings.BET_INVALID.format(
                        minimum=fmt_number(minimum),
                        maximum=fmt_number(maximum),
                        currency=config.CURRENCY,
                    )
                ),
                ephemeral=True,
            )
            return False

        charged = await self.bot.db.try_spend(ctx.author.id, ctx.guild.id, amount, TxReason.BET)
        if not charged:
            await ctx.send(embed=embeds.error(strings.BET_INSUFFICIENT), ephemeral=True)
            return False
        return True

    async def _payout(self, ctx: commands.Context, amount: int) -> int:
        """Credit winnings and return the resulting balance."""
        assert ctx.guild is not None
        if amount > 0:
            return await self.bot.db.add_faith(
                ctx.author.id, ctx.guild.id, amount, TxReason.PAYOUT
            )
        return await self.bot.db.get_balance(ctx.author.id, ctx.guild.id)

    async def _send_result(
        self, ctx: commands.Context, title: str, description: str, won: bool, balance: int
    ) -> None:
        color = config.EMBED_COLOR_SUCCESS if won else config.EMBED_COLOR_ERROR
        embed = embeds.base(title, description, color)
        embed.set_footer(
            text=strings.BALANCE_AFTER.format(
                balance=fmt_number(balance), currency=config.CURRENCY
            ).replace("**", "")
        )
        await ctx.send(embed=embeds.with_author(embed, ctx.author))

    @commands.hybrid_command(
        name="danmaku_flip", description="Duelo rápido a cara o cruz apostando Fe."
    )
    @commands.guild_only()
    @commands.cooldown(1, config.GAME_COOLDOWN_SECONDS, commands.BucketType.user)
    async def danmaku_flip(
        self, ctx: commands.Context, amount: int, side: Literal["cara", "cruz"]
    ) -> None:
        if not await self._take_bet(ctx, amount):
            return

        result = random.choice(("cara", "cruz"))
        won = result == side
        payout = amount * 2 if won else 0
        balance = await self._payout(ctx, payout)

        description = (
            strings.FLIP_WIN.format(
                result=result, amount=fmt_number(payout - amount), currency=config.CURRENCY
            )
            if won
            else strings.FLIP_LOSS.format(
                result=result, amount=fmt_number(amount), currency=config.CURRENCY
            )
        )
        await self._send_result(ctx, strings.FLIP_TITLE, description, won, balance)

    @commands.hybrid_command(
        name="kappa_slots", description="Tira de la tragaperras de Nitori apostando Fe."
    )
    @commands.guild_only()
    @commands.cooldown(1, config.GAME_COOLDOWN_SECONDS, commands.BucketType.user)
    async def kappa_slots(self, ctx: commands.Context, amount: int) -> None:
        if not await self._take_bet(ctx, amount):
            return

        weights = [symbol.weight for symbol in SLOT_SYMBOLS]
        reels = random.choices(SLOT_SYMBOLS, weights=weights, k=3)
        reel_line = " | ".join(symbol.emoji for symbol in reels)

        multiplier, matched = _slots_outcome(reels)
        payout = amount * multiplier
        balance = await self._payout(ctx, payout)

        if multiplier > PAIR_MULTIPLIER and matched is not None:
            description = strings.SLOTS_JACKPOT.format(
                symbol=matched.emoji,
                amount=fmt_number(payout - amount),
                currency=config.CURRENCY,
                multiplier=multiplier,
            )
        elif multiplier == PAIR_MULTIPLIER and matched is not None:
            description = strings.SLOTS_PAIR.format(symbol=matched.emoji)
        else:
            description = strings.SLOTS_LOSS.format(
                amount=fmt_number(amount), currency=config.CURRENCY
            )

        await self._send_result(
            ctx,
            strings.SLOTS_TITLE,
            f"# {reel_line}\n{description}",
            multiplier > 0,
            balance,
        )

    @commands.hybrid_command(
        name="roulette", description="Apuesta a color o a un rango en la ruleta de Gensokyo."
    )
    @commands.guild_only()
    @commands.cooldown(1, config.GAME_COOLDOWN_SECONDS, commands.BucketType.user)
    async def roulette(self, ctx: commands.Context, amount: int, bet: str) -> None:
        choice = bet.strip().lower()
        if choice not in {"rojo", "negro", *ROULETTE_RANGES}:
            await ctx.send(embed=embeds.error(strings.ROULETTE_BAD_BET), ephemeral=True)
            return
        if not await self._take_bet(ctx, amount):
            return

        number = random.randrange(ROULETTE_SLOTS)
        color = _roulette_color(number)
        multiplier = _roulette_multiplier(choice, number, color)
        payout = amount * multiplier
        balance = await self._payout(ctx, payout)

        outcome = (
            strings.ROULETTE_WIN.format(
                amount=fmt_number(payout - amount), currency=config.CURRENCY
            )
            if multiplier
            else strings.ROULETTE_LOSS.format(
                amount=fmt_number(amount), currency=config.CURRENCY
            )
        )
        description = (
            strings.ROULETTE_RESULT.format(number=number, color=color) + "\n" + outcome
        )
        await self._send_result(
            ctx, strings.ROULETTE_TITLE, description, bool(multiplier), balance
        )


def _slots_outcome(reels: list[SlotSymbol]) -> tuple[int, SlotSymbol | None]:
    """Return the payout multiplier and the symbol that produced it."""
    first, second, third = reels
    if first is second is third:
        return first.triple_multiplier, first
    for candidate in (first, second, third):
        if reels.count(candidate) == 2:
            return PAIR_MULTIPLIER, candidate
    return 0, None


def _roulette_color(number: int) -> str:
    if number == 0:
        return "verde"
    return "rojo" if number in ROULETTE_RED else "negro"


def _roulette_multiplier(choice: str, number: int, color: str) -> int:
    if choice in ROULETTE_RANGES:
        return ROULETTE_RANGE_MULTIPLIER if number in ROULETTE_RANGES[choice] else 0
    return ROULETTE_COLOR_MULTIPLIER if choice == color else 0


async def setup(bot: "KourindouBot") -> None:
    await bot.add_cog(GamesCog(bot))
