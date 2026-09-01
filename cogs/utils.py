"""Server utilities: team splitting, squad calls and quotes."""

import logging
import random
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

import config
import strings
from core import embeds
from core.timeutils import utcnow_ts
from database.models import Squad, SquadStatus

if TYPE_CHECKING:
    from main import KourindouBot

logger = logging.getLogger(__name__)

MAX_TEAMS = 10
QUOTE_MAX_LENGTH = 500
QUOTE_LIST_LIMIT = 10
SQUAD_SWEEP_MINUTES = 30


async def build_squad_embed(
    bot: "KourindouBot", guild: discord.Guild, squad: Squad
) -> discord.Embed:
    signups = await bot.db.get_squad_signups(squad.message_id)
    host = guild.get_member(squad.host_id)
    embed = embeds.base(
        strings.SQUAD_TITLE.format(game=squad.game),
        strings.SQUAD_HOST.format(host=host.mention if host else f"<@{squad.host_id}>"),
    )
    if squad.scheduled_at:
        embed.description += "\n" + strings.SQUAD_TIME.format(time=squad.scheduled_at)

    labels = (
        (SquadStatus.IN, strings.SQUAD_LIST_IN),
        (SquadStatus.LATE, strings.SQUAD_LIST_LATE),
        (SquadStatus.OUT, strings.SQUAD_LIST_OUT),
    )
    for status, label in labels:
        user_ids = signups.get(status.value, [])
        names = [
            member.display_name if (member := guild.get_member(uid)) else f"<@{uid}>"
            for uid in user_ids
        ]
        embed.add_field(
            name=label.format(count=len(user_ids)),
            value="\n".join(f"• {name}" for name in names) or strings.SQUAD_NOBODY,
            inline=True,
        )
    if squad.closed:
        embed.set_footer(text=strings.SQUAD_CLOSED)
    return embed


class SquadView(discord.ui.View):
    """Persistent view: the buttons keep working after a restart."""

    def __init__(self, bot: "KourindouBot") -> None:
        super().__init__(timeout=None)
        self.bot = bot

    async def _respond(self, interaction: discord.Interaction, status: SquadStatus) -> None:
        if interaction.message is None or interaction.guild is None:
            return
        squad = await self.bot.db.get_squad(interaction.message.id)
        if squad is None or squad.closed:
            await interaction.response.send_message(strings.SQUAD_CLOSED, ephemeral=True)
            return

        await self.bot.db.set_squad_signup(interaction.message.id, interaction.user.id, status)
        embed = await build_squad_embed(self.bot, interaction.guild, squad)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label=strings.SQUAD_IN, style=discord.ButtonStyle.success, custom_id="squad:in"
    )
    async def join(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._respond(interaction, SquadStatus.IN)

    @discord.ui.button(
        label=strings.SQUAD_LATE, style=discord.ButtonStyle.primary, custom_id="squad:late"
    )
    async def late(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._respond(interaction, SquadStatus.LATE)

    @discord.ui.button(
        label=strings.SQUAD_OUT, style=discord.ButtonStyle.secondary, custom_id="squad:out"
    )
    async def out(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._respond(interaction, SquadStatus.OUT)


class UtilsCog(commands.Cog, name="Utilidades"):
    def __init__(self, bot: "KourindouBot") -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(SquadView(self.bot))
        self.sweep_squads.start()

    async def cog_unload(self) -> None:
        self.sweep_squads.cancel()

    # ------------------------------------------------------------------ teams

    @commands.hybrid_command(
        name="teams", description="Reparte a los miembros del canal de voz en equipos."
    )
    @commands.guild_only()
    async def teams(self, ctx: commands.Context, equipos: int = 2) -> None:
        voice_state = getattr(ctx.author, "voice", None)
        if voice_state is None or voice_state.channel is None:
            await ctx.send(embed=embeds.error(strings.TEAMS_NOT_IN_VOICE), ephemeral=True)
            return

        members = [member for member in voice_state.channel.members if not member.bot]
        if not 2 <= equipos <= MAX_TEAMS:
            await ctx.send(
                embed=embeds.error(strings.TEAMS_TOO_MANY.format(maximum=MAX_TEAMS)),
                ephemeral=True,
            )
            return
        if len(members) < equipos:
            await ctx.send(
                embed=embeds.error(strings.TEAMS_NOT_ENOUGH.format(needed=equipos)),
                ephemeral=True,
            )
            return

        random.shuffle(members)
        # Dealing round robin keeps the team sizes within one member of each other.
        buckets = [members[index::equipos] for index in range(equipos)]

        embed = embeds.base(strings.TEAMS_TITLE, f"Canal: **{voice_state.channel.name}**")
        for index, bucket in enumerate(buckets, start=1):
            embed.add_field(
                name=strings.TEAMS_TEAM_NAME.format(index=index),
                value="\n".join(f"• {member.display_name}" for member in bucket),
                inline=True,
            )
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------ squad

    @commands.hybrid_command(name="squad", description="Convoca una partida con botones.")
    @commands.guild_only()
    async def squad(self, ctx: commands.Context, juego: str, hora: str | None = None) -> None:
        assert ctx.guild is not None
        view = SquadView(self.bot)
        placeholder = Squad(
            message_id=0,
            guild_id=ctx.guild.id,
            channel_id=ctx.channel.id,
            host_id=ctx.author.id,
            game=juego,
            scheduled_at=hora,
            created_at=utcnow_ts(),
            closed=False,
        )
        embed = await build_squad_embed(self.bot, ctx.guild, placeholder)
        message = await ctx.send(embed=embed, view=view)

        await self.bot.db.create_squad(
            message.id, ctx.guild.id, ctx.channel.id, ctx.author.id, juego, hora
        )
        logger.info(
            "Squad created | guild=%s host=%s message=%s game=%r",
            ctx.guild.id,
            ctx.author.id,
            message.id,
            juego,
        )

    @tasks.loop(minutes=SQUAD_SWEEP_MINUTES)
    async def sweep_squads(self) -> None:
        cutoff = utcnow_ts() - config.SQUAD_LIFETIME_SECONDS
        for message_id in await self.bot.db.expire_squads(cutoff):
            await self._disable_squad_message(message_id)

    @sweep_squads.before_loop
    async def before_sweep_squads(self) -> None:
        await self.bot.wait_until_ready()

    async def _disable_squad_message(self, message_id: int) -> None:
        squad = await self.bot.db.get_squad(message_id)
        if squad is None:
            return
        channel = self.bot.get_channel(squad.channel_id)
        guild = self.bot.get_guild(squad.guild_id)
        if not isinstance(channel, discord.abc.Messageable) or guild is None:
            return
        try:
            message = await channel.fetch_message(message_id)
            embed = await build_squad_embed(self.bot, guild, squad)
            await message.edit(embed=embed, view=None)
        except discord.HTTPException:
            logger.debug("Expired squad message could not be edited | message=%s", message_id)

    # ----------------------------------------------------------------- quotes

    @commands.hybrid_command(name="addquote", description="Registra una frase célebre.")
    @commands.guild_only()
    async def addquote(
        self, ctx: commands.Context, member: discord.Member, *, texto: str
    ) -> None:
        assert ctx.guild is not None
        if len(texto) > QUOTE_MAX_LENGTH:
            await ctx.send(
                embed=embeds.error(strings.QUOTE_TOO_LONG.format(maximum=QUOTE_MAX_LENGTH)),
                ephemeral=True,
            )
            return

        # Slash invocations have no real source message to link back to.
        jump_url = getattr(ctx.message, "jump_url", None) if ctx.interaction is None else None
        quote_id = await self.bot.db.add_quote(
            ctx.guild.id, member.id, ctx.author.id, texto, jump_url
        )
        await ctx.send(
            embed=embeds.success("💬", strings.QUOTE_ADDED.format(quote_id=quote_id))
        )

    @commands.hybrid_command(name="quote", description="Muestra una frase aleatoria.")
    @commands.guild_only()
    async def quote(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        assert ctx.guild is not None
        found = await self.bot.db.random_quote(ctx.guild.id, member.id if member else None)
        if found is None:
            await ctx.send(embed=embeds.error(strings.QUOTE_EMPTY), ephemeral=True)
            return

        author = ctx.guild.get_member(found.author_id)
        name = author.display_name if author else f"<@{found.author_id}>"
        embed = embeds.base(strings.QUOTE_TITLE, f"> {found.content}\n\n— **{name}**")
        embed.set_footer(text=f"#{found.quote_id}")
        if author is not None:
            embed.set_thumbnail(url=author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="quotes", description="Lista las frases registradas.")
    @commands.guild_only()
    async def quotes(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        assert ctx.guild is not None
        found = await self.bot.db.list_quotes(
            ctx.guild.id, member.id if member else None, QUOTE_LIST_LIMIT
        )
        if not found:
            await ctx.send(embed=embeds.error(strings.QUOTE_EMPTY), ephemeral=True)
            return

        lines = []
        for entry in found:
            author = ctx.guild.get_member(entry.author_id)
            name = author.display_name if author else f"<@{entry.author_id}>"
            excerpt = entry.content if len(entry.content) <= 80 else entry.content[:77] + "..."
            lines.append(f"`#{entry.quote_id}` **{name}**: {excerpt}")
        await ctx.send(embed=embeds.base(strings.QUOTE_LIST_TITLE, "\n".join(lines)))

    @commands.hybrid_command(name="delquote", description="Elimina una frase por su número.")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def delquote(self, ctx: commands.Context, quote_id: int) -> None:
        assert ctx.guild is not None
        deleted = await self.bot.db.delete_quote(quote_id, ctx.guild.id)
        message = (
            strings.QUOTE_DELETED.format(quote_id=quote_id)
            if deleted
            else strings.QUOTE_NOT_FOUND
        )
        embed = embeds.success("🗑️", message) if deleted else embeds.error(message)
        await ctx.send(embed=embed, ephemeral=not deleted)


async def setup(bot: "KourindouBot") -> None:
    await bot.add_cog(UtilsCog(bot))
