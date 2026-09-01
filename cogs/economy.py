"""Faith economy: daily offering, balance, transfers and leaderboard."""

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

import config
import strings
from core import embeds
from core.text import fmt_number
from core.timeutils import format_duration, utcnow_ts
from database.models import TransferResult

if TYPE_CHECKING:
    from main import KourindouBot

logger = logging.getLogger(__name__)


class EconomyCog(commands.Cog, name="Economía"):
    def __init__(self, bot: "KourindouBot") -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="daily", description="Haz tu ofrenda diaria en el Santuario Hakurei."
    )
    @commands.guild_only()
    async def daily(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        result = await self.bot.db.try_claim_daily(ctx.author.id, ctx.guild.id)

        if not result.granted:
            remaining = format_duration(result.remaining_seconds)
            await ctx.send(
                embed=embeds.error(strings.DAILY_COOLDOWN.format(remaining=remaining)),
                ephemeral=True,
            )
            return

        description = strings.DAILY_SUCCESS.format(
            amount=fmt_number(result.amount), currency=config.CURRENCY
        )
        embed = embeds.success(strings.DAILY_TITLE, description)
        if result.bonus:
            embed.add_field(
                name="Racha",
                value=strings.DAILY_STREAK.format(
                    streak=result.streak, bonus=fmt_number(result.bonus), currency=config.CURRENCY
                ),
                inline=False,
            )
        embed.set_footer(
            text=strings.BALANCE_AFTER.format(
                balance=fmt_number(result.new_balance), currency=config.CURRENCY
            ).replace("**", "")
        )
        await ctx.send(embed=embeds.with_author(embed, ctx.author))
        logger.info(
            "Daily claimed | guild=%s user=%s amount=%s streak=%s",
            ctx.guild.id,
            ctx.author.id,
            result.amount,
            result.streak,
        )

    @commands.hybrid_command(
        name="faith", aliases=["balance"], description="Consulta los Puntos de Fe acumulados."
    )
    @commands.guild_only()
    async def faith(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        assert ctx.guild is not None
        target = member or ctx.author
        await self.bot.db.ensure_user(target.id, ctx.guild.id)
        profile = await self.bot.db.get_profile(target.id, ctx.guild.id)
        rank = await self.bot.db.get_rank(target.id, ctx.guild.id)

        balance = profile["faith_points"] if profile else 0
        embed = embeds.base(
            strings.BALANCE_TITLE,
            strings.BALANCE_LINE.format(amount=fmt_number(balance), currency=config.CURRENCY),
        )
        embed.add_field(name="Ranking", value=strings.BALANCE_RANK.format(rank=rank), inline=True)
        if profile and profile["voice_minutes"]:
            embed.add_field(
                name="Voz",
                value=strings.BALANCE_VOICE.format(minutes=fmt_number(profile["voice_minutes"])),
                inline=True,
            )
        if profile and profile["daily_streak"]:
            streak_value = f"**{profile['daily_streak']}** días"
            embed.add_field(name="Racha diaria", value=streak_value, inline=True)
        await ctx.send(embed=embeds.with_author(embed, target))

    @commands.hybrid_command(
        name="wallet",
        aliases=["cartera", "monedero"],
        description="Consulta tu monedero personal de forma privada (Fe y BreakCoins).",
    )
    @commands.guild_only()
    async def wallet(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        target = ctx.author
        wallet = await self.bot.db.get_wallet(target.id, ctx.guild.id)

        title = strings.WALLET_TITLE.format(user=target.display_name)
        embed = embeds.base(title)
        embed.add_field(
            name=strings.WALLET_FAITH_FIELD,
            value=strings.BALANCE_LINE.format(
                amount=fmt_number(wallet.faith_points), currency=config.CURRENCY
            ),
            inline=True,
        )
        embed.add_field(
            name=strings.WALLET_BREAKCOIN_FIELD,
            value=strings.BALANCE_LINE.format(
                amount=fmt_number(wallet.breakcoins), currency=config.CURRENCY_BREAKCOIN
            ),
            inline=True,
        )
        embed.add_field(
            name="Ranking de Fe",
            value=strings.BALANCE_RANK.format(rank=wallet.rank),
            inline=True,
        )
        if wallet.voice_minutes:
            embed.add_field(
                name="Voz",
                value=strings.BALANCE_VOICE.format(minutes=fmt_number(wallet.voice_minutes)),
                inline=True,
            )
        if wallet.daily_streak:
            streak_value = f"**{wallet.daily_streak}** días"
            embed.add_field(name="Racha diaria", value=streak_value, inline=True)

        await ctx.send(embed=embeds.with_author(embed, target), ephemeral=True)

    @commands.hybrid_command(
        name="transfer", aliases=["pay"], description="Dona Puntos de Fe a otro miembro."
    )
    @commands.guild_only()
    async def transfer(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        assert ctx.guild is not None
        minimum = await self.bot.db.get_setting(ctx.guild.id, "transfer_min_amount")

        if member.bot:
            await self._reject(ctx, strings.TRANSFER_TO_BOT)
            return
        if member.id == ctx.author.id:
            await self._reject(ctx, strings.TRANSFER_TO_SELF)
            return
        if amount < minimum:
            await self._reject(ctx, strings.TRANSFER_INVALID_AMOUNT.format(minimum=minimum))
            return

        result, net = await self.bot.db.transfer_faith(
            ctx.author.id, member.id, ctx.guild.id, amount
        )

        if result is TransferResult.INSUFFICIENT_FUNDS:
            balance = await self.bot.db.get_balance(ctx.author.id, ctx.guild.id)
            await self._reject(
                ctx,
                strings.TRANSFER_INSUFFICIENT.format(
                    balance=fmt_number(balance), currency=config.CURRENCY
                ),
            )
            return
        if result is TransferResult.ACCOUNT_TOO_YOUNG:
            await self._reject(ctx, await self._account_age_message(ctx))
            return

        embed = embeds.success(
            "🎁 Donación",
            strings.TRANSFER_SUCCESS.format(
                amount=fmt_number(net), currency=config.CURRENCY, receiver=member.mention
            ),
        )
        fee = amount - net
        if fee:
            embed.set_footer(
                text=strings.TRANSFER_FEE_NOTE.format(
                    fee=fmt_number(fee), currency=config.CURRENCY
                ).replace("**", "")
            )
        await ctx.send(embed=embeds.with_author(embed, ctx.author))

    @commands.hybrid_command(
        name="leaderboard", aliases=["top"], description="Los miembros con más Fe del servidor."
    )
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        entries = await self.bot.db.get_leaderboard(ctx.guild.id, config.LEADERBOARD_LIMIT)
        if not entries:
            await ctx.send(embed=embeds.error(strings.LEADERBOARD_EMPTY), ephemeral=True)
            return

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for entry in entries:
            member = ctx.guild.get_member(entry.user_id)
            name = member.display_name if member else f"<@{entry.user_id}>"
            marker = medals.get(entry.rank, f"`#{entry.rank}`")
            lines.append(
                f"{marker} **{name}** — {fmt_number(entry.faith_points)} {config.CURRENCY}"
            )

        embed = embeds.base(strings.LEADERBOARD_TITLE, "\n".join(lines))
        if not any(entry.user_id == ctx.author.id for entry in entries):
            rank = await self.bot.db.get_rank(ctx.author.id, ctx.guild.id)
            balance = await self.bot.db.get_balance(ctx.author.id, ctx.guild.id)
            embed.set_footer(
                text=strings.LEADERBOARD_YOU.format(
                    rank=rank, amount=fmt_number(balance), currency=config.CURRENCY
                ).replace("**", "")
            )
        await ctx.send(embed=embed)

    async def _reject(self, ctx: commands.Context, message: str) -> None:
        await ctx.send(embed=embeds.error(message), ephemeral=True)

    async def _account_age_message(self, ctx: commands.Context) -> str:
        assert ctx.guild is not None
        min_age = await self.bot.db.get_setting(ctx.guild.id, "transfer_min_account_age_seconds")
        profile = await self.bot.db.get_profile(ctx.author.id, ctx.guild.id)
        elapsed = utcnow_ts() - profile["created_at"] if profile else 0
        return strings.TRANSFER_TOO_YOUNG.format(remaining=format_duration(min_age - elapsed))


async def setup(bot: "KourindouBot") -> None:
    await bot.add_cog(EconomyCog(bot))
