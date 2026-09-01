"""Passive faith rewards for chatting and for sitting in voice channels."""

import logging
import random
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

import config

if TYPE_CHECKING:
    from main import KourindouBot

logger = logging.getLogger(__name__)


class ActivityCog(commands.Cog, name="Actividad"):
    def __init__(self, bot: "KourindouBot") -> None:
        self.bot = bot
        self.settle_voice.start()

    async def cog_unload(self) -> None:
        self.settle_voice.cancel()

    # ------------------------------------------------------------------- chat

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        guild_id = message.guild.id
        min_length = await self.bot.db.get_setting(guild_id, "chat_min_length")
        if len(message.content.strip()) < min_length:
            return
        if await self._is_excluded_channel(guild_id, message.channel.id):
            return

        # Command invocations are not chat activity.
        context = await self.bot.get_context(message)
        if context.valid:
            return

        low = await self.bot.db.get_setting(guild_id, "chat_reward_min")
        high = await self.bot.db.get_setting(guild_id, "chat_reward_max")
        cooldown = await self.bot.db.get_setting(guild_id, "chat_cooldown_seconds")
        amount = random.randint(min(low, high), max(low, high))
        await self.bot.db.try_award_chat(message.author.id, guild_id, amount, cooldown)

    async def _is_excluded_channel(self, guild_id: int, channel_id: int) -> bool:
        raw = await self.bot.db.get_text_setting(guild_id, config.EXCLUDED_CHANNELS_KEY)
        if not raw:
            return False
        return str(channel_id) in {part.strip() for part in raw.split(",")}

    # ------------------------------------------------------------------ voice

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return
        guild_id = member.guild.id

        if after.channel is None:
            # member.voice is already cleared here, so the payout is judged on the
            # channel being left, counting the member as still present.
            await self._settle(member, before.channel, before)
            await self.bot.db.close_voice_session(member.id, guild_id)
            return

        if before.channel is not None and before.channel.id != after.channel.id:
            await self._settle(member, before.channel, before)

        await self.bot.db.open_voice_session(member.id, guild_id, after.channel.id)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self._reconcile_sessions()

    async def _reconcile_sessions(self) -> None:
        """Align stored sessions with who is actually connected right now."""
        for guild in self.bot.guilds:
            live = {
                member.id: channel.id
                for channel in guild.voice_channels
                for member in channel.members
                if not member.bot
            }
            stored = {
                session.user_id for session in await self.bot.db.list_voice_sessions(guild.id)
            }
            for user_id in stored - live.keys():
                await self.bot.db.close_voice_session(user_id, guild.id)
            for user_id in live.keys() - stored:
                await self.bot.db.open_voice_session(user_id, guild.id, live[user_id])
            if stored != live.keys():
                logger.info(
                    "Voice sessions reconciled | guild=%s stored=%s live=%s",
                    guild.id,
                    len(stored),
                    len(live),
                )

    @tasks.loop(minutes=config.VOICE_SETTLE_INTERVAL_MINUTES)
    async def settle_voice(self) -> None:
        for guild in self.bot.guilds:
            per_minute = await self.bot.db.get_setting(guild.id, "voice_faith_per_minute")
            min_humans = await self.bot.db.get_setting(guild.id, "voice_min_humans")
            for session in await self.bot.db.list_voice_sessions(guild.id):
                member = guild.get_member(session.user_id)
                if member is None or member.voice is None or member.voice.channel is None:
                    await self.bot.db.close_voice_session(session.user_id, guild.id)
                    continue
                await self._settle(
                    member, member.voice.channel, member.voice, per_minute, min_humans
                )

    @settle_voice.before_loop
    async def before_settle_voice(self) -> None:
        await self.bot.wait_until_ready()

    async def _settle(
        self,
        member: discord.Member,
        channel: discord.abc.Connectable | None,
        state: discord.VoiceState,
        per_minute: int | None = None,
        min_humans: int | None = None,
    ) -> None:
        """Pay out the whole minutes accrued, discarding the ones that do not qualify."""
        guild_id = member.guild.id
        minutes = await self.bot.db.consume_voice_minutes(member.id, guild_id)
        if minutes <= 0:
            return
        if min_humans is None:
            min_humans = await self.bot.db.get_setting(guild_id, "voice_min_humans")
        if not _is_eligible(member, channel, state, min_humans):
            return
        if per_minute is None:
            per_minute = await self.bot.db.get_setting(guild_id, "voice_faith_per_minute")
        await self.bot.db.award_voice(member.id, guild_id, minutes, minutes * per_minute)


def _is_eligible(
    member: discord.Member,
    channel: discord.abc.Connectable | None,
    state: discord.VoiceState,
    min_humans: int,
) -> bool:
    """Faith is only paid for real company: not alone, not deafened, not in AFK."""
    if not isinstance(channel, discord.VoiceChannel | discord.StageChannel):
        return False
    afk_channel = member.guild.afk_channel
    if afk_channel is not None and channel.id == afk_channel.id:
        return False
    if state.deaf or state.self_deaf:
        return False
    # The member counts as present even when the cache already removed them.
    humans = {other.id for other in channel.members if not other.bot} | {member.id}
    return len(humans) >= min_humans


async def setup(bot: "KourindouBot") -> None:
    await bot.add_cog(ActivityCog(bot))
