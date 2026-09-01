"""Entry point: builds the bot, loads cogs and owns the global error handling."""

import asyncio
import logging
import logging.handlers
from contextlib import suppress

import discord
from discord import app_commands
from discord.ext import commands

import config
import strings
from core import embeds
from core.timeutils import format_duration
from database.db_manager import Database

logger = logging.getLogger("kourindou")


def setup_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.handlers.RotatingFileHandler(
        config.LOG_DIR / "kourindou.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(config.LOG_LEVEL)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    logging.getLogger("discord").setLevel(logging.WARNING)


async def resolve_prefix(bot: "KourindouBot", message: discord.Message) -> list[str]:
    prefix = config.COMMAND_PREFIX
    if message.guild is not None:
        prefix = await bot.db.get_text_setting(
            message.guild.id, "command_prefix", config.COMMAND_PREFIX
        )
    return commands.when_mentioned_or(prefix)(bot, message)


class KourindouBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        super().__init__(
            command_prefix=resolve_prefix,
            intents=intents,
            help_command=commands.DefaultHelpCommand(no_category="Comandos"),
            case_insensitive=True,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
        )
        self.db = Database(config.DATABASE_PATH, config.SCHEMA_PATH)
        # The tree does not inherit the bot's handler; it has to be wired explicitly.
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self) -> None:
        await self.db.connect()
        for extension in config.COGS:
            try:
                await self.load_extension(extension)
                logger.info("Cog loaded | name=%s", extension)
            except commands.ExtensionError:
                logger.exception("Cog failed to load | name=%s", extension)

        if config.DEV_GUILD_ID is not None:
            guild = discord.Object(id=config.DEV_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Commands synced to dev guild | guild=%s count=%s", guild.id, len(synced))
        else:
            synced = await self.tree.sync()
            logger.info("Commands synced globally | count=%s", len(synced))

    async def on_ready(self) -> None:
        logger.info(
            "Connected | user=%s id=%s guilds=%s",
            self.user,
            getattr(self.user, "id", None),
            len(self.guilds),
        )
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="el Santuario Hakurei 🌸"
            )
        )

    async def close(self) -> None:
        await self.db.close()
        await super().close()

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        message = _expected_error_message(error)
        if message is None:
            logger.exception(
                "Unhandled command error | command=%s user=%s guild=%s",
                getattr(ctx.command, "qualified_name", "?"),
                ctx.author.id,
                getattr(ctx.guild, "id", None),
                exc_info=error,
            )
            message = strings.ERROR_GENERIC
        # The channel may be gone or the interaction expired; delivery is best effort.
        with suppress(discord.HTTPException):
            await ctx.send(embed=embeds.error(message), ephemeral=True)

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        message = _expected_app_error_message(error)
        if message is None:
            logger.exception(
                "Unhandled app command error | command=%s user=%s guild=%s",
                getattr(interaction.command, "qualified_name", "?"),
                interaction.user.id,
                getattr(interaction.guild, "id", None),
                exc_info=error,
            )
            message = strings.ERROR_GENERIC
        with suppress(discord.HTTPException):
            if interaction.response.is_done():
                await interaction.followup.send(embed=embeds.error(message), ephemeral=True)
            else:
                await interaction.response.send_message(
                    embed=embeds.error(message), ephemeral=True
                )


def _expected_error_message(error: Exception) -> str | None:
    """Map a known user mistake to its message. None means it is a real failure."""
    if isinstance(error, commands.CommandOnCooldown):
        return strings.ERROR_COOLDOWN.format(remaining=format_duration(int(error.retry_after) + 1))
    if isinstance(error, commands.NoPrivateMessage):
        return strings.ERROR_GUILD_ONLY
    if isinstance(error, commands.CheckFailure):
        return strings.ERROR_MISSING_PERMS
    if isinstance(error, commands.UserInputError):
        return strings.ERROR_BAD_ARGUMENT
    if isinstance(error, commands.CommandInvokeError):
        return _expected_error_message(error.original)
    return None


def _expected_app_error_message(error: app_commands.AppCommandError) -> str | None:
    if isinstance(error, app_commands.CommandOnCooldown):
        return strings.ERROR_COOLDOWN.format(remaining=format_duration(int(error.retry_after) + 1))
    if isinstance(error, app_commands.CheckFailure):
        return strings.ERROR_MISSING_PERMS
    if isinstance(error, app_commands.TransformerError):
        return strings.ERROR_BAD_ARGUMENT
    return None


async def main() -> None:
    setup_logging()
    bot = KourindouBot()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by the operator")
