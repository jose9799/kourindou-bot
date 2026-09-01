"""Health and information commands."""

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

import config
from core import embeds

if TYPE_CHECKING:
    from main import KourindouBot

logger = logging.getLogger(__name__)


class GeneralCog(commands.Cog, name="General"):
    def __init__(self, bot: "KourindouBot") -> None:
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Comprueba que el bot responde.")
    async def ping(self, ctx: commands.Context) -> None:
        latency_ms = round(self.bot.latency * 1000)
        await ctx.send(
            embed=embeds.base("🏓 Pong", f"Latencia con Gensokyo: **{latency_ms} ms**"),
            ephemeral=True,
        )

    @commands.hybrid_command(name="kourindou", description="Información sobre el bot.")
    async def about(self, ctx: commands.Context) -> None:
        embed = embeds.base(
            "🏮 Kourindou Bot",
            "Bot temático de *Touhou Project* para **Gensokyolis:Re**.\n"
            f"Moneda del servidor: {config.CURRENCY} **{config.CURRENCY_NAME}**.",
        )
        embed.add_field(
            name="Economía",
            value="`/daily` `/faith` `/transfer` `/leaderboard`",
            inline=False,
        )
        embed.add_field(name="Tienda", value="`/shop` `/inventory`", inline=False)
        embed.add_field(
            name="Juegos",
            value="`/danmaku_flip` `/kappa_slots` `/roulette`",
            inline=False,
        )
        embed.add_field(
            name="Utilidades", value="`/teams` `/squad` `/quote` `/addquote`", inline=False
        )
        embed.set_footer(text=f"Servidores: {len(self.bot.guilds)}")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info(
            "Joined guild | guild=%s name=%s members=%s", guild.id, guild.name, guild.member_count
        )


async def setup(bot: "KourindouBot") -> None:
    await bot.add_cog(GeneralCog(bot))
