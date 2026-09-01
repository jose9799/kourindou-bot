"""Embed builders. Commands orchestrate, these present."""

import discord

import config


def base(title: str, description: str = "", color: int = config.EMBED_COLOR) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def success(title: str, description: str = "") -> discord.Embed:
    return base(title, description, config.EMBED_COLOR_SUCCESS)


def error(description: str) -> discord.Embed:
    return base("", description, config.EMBED_COLOR_ERROR)


def with_author(embed: discord.Embed, member: discord.abc.User) -> discord.Embed:
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    return embed
