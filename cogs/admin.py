"""Server administration: settings, catalogue management and economy audits."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import discord
from discord.ext import commands

import config
import strings
from core import embeds
from core.text import fmt_number
from database.models import ItemKind, TxReason

if TYPE_CHECKING:
    from main import KourindouBot

logger = logging.getLogger(__name__)

TEXT_KEYS = ("command_prefix", config.EXCLUDED_CHANNELS_KEY)

# Catalogue seeded by /shopadmin seed. Roles are left out on purpose: their ids
# are server specific and must be added one by one with the payload argument.
SEED_ITEMS = (
    ("Linterna de Kourindou", 250, ItemKind.COSMETIC, "Elige el juego de la noche."),
    ("Ofrenda del Santuario", 500, ItemKind.PERK, "Acceso al canal VIP del santuario."),
    ("Cámara del Bunbunmaru", 750, ItemKind.PERK, "Permiso para adjuntar imágenes y archivos."),
    ("Altavoz de Nitori", 1000, ItemKind.PERK, "Uso del Soundboard en los canales de voz."),
    ("Sello de la Barrera", 2500, ItemKind.COSMETIC, "Elige el icono temporal del servidor."),
)


class AdminCog(commands.Cog, name="Administración"):
    def __init__(self, bot: "KourindouBot") -> None:
        self.bot = bot

    # ----------------------------------------------------------------- config

    @commands.hybrid_group(
        name="config", fallback="view", description="Configuración del servidor."
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def config_group(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        overrides = await self.bot.db.list_settings(ctx.guild.id)
        lines = [
            f"`{key}` = **{overrides.get(key, default)}**"
            + ("" if key in overrides else " *(por defecto)*")
            for key, default in config.SETTING_DEFAULTS.items()
        ]
        lines += [f"`{key}` = **{overrides[key]}**" for key in TEXT_KEYS if key in overrides]
        await ctx.send(embed=embeds.base(strings.ADMIN_CONFIG_TITLE, "\n".join(lines)))

    @config_group.command(name="set", description="Cambia un valor de configuración.")
    async def config_set(self, ctx: commands.Context, key: str, value: str) -> None:
        assert ctx.guild is not None
        key = key.strip().lower()
        if key not in config.SETTING_DEFAULTS and key not in TEXT_KEYS:
            await self._unknown_key(ctx)
            return
        if key in config.SETTING_DEFAULTS and not _is_integer(value):
            await ctx.send(embed=embeds.error(strings.ADMIN_CONFIG_BAD_VALUE), ephemeral=True)
            return

        await self.bot.db.set_setting(ctx.guild.id, key, value)
        await ctx.send(
            embed=embeds.success(
                strings.ADMIN_CONFIG_TITLE, strings.ADMIN_CONFIG_SET.format(key=key, value=value)
            )
        )

    @config_group.command(name="reset", description="Devuelve un valor a su defecto.")
    async def config_reset(self, ctx: commands.Context, key: str) -> None:
        assert ctx.guild is not None
        key = key.strip().lower()
        if key not in config.SETTING_DEFAULTS and key not in TEXT_KEYS:
            await self._unknown_key(ctx)
            return
        await self.bot.db.clear_setting(ctx.guild.id, key)
        await ctx.send(
            embed=embeds.success(
                strings.ADMIN_CONFIG_TITLE, strings.ADMIN_CONFIG_CLEARED.format(key=key)
            )
        )

    async def _unknown_key(self, ctx: commands.Context) -> None:
        keys = ", ".join(f"`{key}`" for key in (*config.SETTING_DEFAULTS, *TEXT_KEYS))
        await ctx.send(
            embed=embeds.error(strings.ADMIN_CONFIG_UNKNOWN.format(keys=keys)), ephemeral=True
        )

    # ------------------------------------------------------------------- shop

    @commands.hybrid_group(
        name="shopadmin", fallback="list", description="Gestiona el catálogo de la tienda."
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def shop_group(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        items = await self.bot.db.list_shop_items(ctx.guild.id, include_disabled=True)
        if not items:
            await ctx.send(embed=embeds.error(strings.SHOP_EMPTY), ephemeral=True)
            return

        lines = [
            f"`#{item.item_id}` **{item.name}** — {fmt_number(item.price)} {config.CURRENCY}"
            f" · {item.kind}{'' if item.enabled else ' · *desactivado*'}"
            for item in items
        ]
        await ctx.send(embed=embeds.base(strings.SHOP_TITLE, "\n".join(lines)))

    @shop_group.command(name="add", description="Añade un artículo al catálogo.")
    async def shop_add(
        self,
        ctx: commands.Context,
        nombre: str,
        precio: int,
        tipo: Literal["role", "perk", "cosmetic", "consumable"],
        rol: discord.Role | None = None,
        stock: int | None = None,
        *,
        descripcion: str | None = None,
    ) -> None:
        assert ctx.guild is not None
        kind = ItemKind(tipo)
        if kind is ItemKind.ROLE:
            if rol is None:
                await ctx.send(
                    embed=embeds.error(strings.ADMIN_ITEM_ROLE_REQUIRED), ephemeral=True
                )
                return
            if not _bot_can_assign(ctx.guild, rol):
                await ctx.send(embed=embeds.error(strings.ADMIN_ROLE_TOO_HIGH), ephemeral=True)
                return

        item_id = await self.bot.db.create_shop_item(
            guild_id=ctx.guild.id,
            name=nombre,
            price=precio,
            kind=kind,
            description=descripcion,
            payload=str(rol.id) if rol else None,
            stock=stock,
        )
        if item_id is None:
            await ctx.send(embed=embeds.error(strings.ADMIN_ITEM_DUPLICATE), ephemeral=True)
            return

        logger.info(
            "Shop item created | guild=%s item=%s name=%r price=%s kind=%s",
            ctx.guild.id,
            item_id,
            nombre,
            precio,
            kind.value,
        )
        await ctx.send(
            embed=embeds.success(
                strings.SHOP_TITLE,
                strings.ADMIN_ITEM_CREATED.format(name=nombre, item_id=item_id),
            )
        )

    @shop_group.command(name="remove", description="Elimina un artículo del catálogo.")
    async def shop_remove(self, ctx: commands.Context, item_id: int) -> None:
        assert ctx.guild is not None
        if not await self.bot.db.delete_shop_item(item_id, ctx.guild.id):
            await ctx.send(embed=embeds.error(strings.ADMIN_ITEM_NOT_FOUND), ephemeral=True)
            return
        await ctx.send(
            embed=embeds.success(
                strings.SHOP_TITLE, strings.ADMIN_ITEM_DELETED.format(item_id=item_id)
            )
        )

    @shop_group.command(name="toggle", description="Activa o desactiva un artículo.")
    async def shop_toggle(self, ctx: commands.Context, item_id: int, activo: bool) -> None:
        assert ctx.guild is not None
        if not await self.bot.db.set_item_enabled(item_id, ctx.guild.id, activo):
            await ctx.send(embed=embeds.error(strings.ADMIN_ITEM_NOT_FOUND), ephemeral=True)
            return
        state = "activo" if activo else "desactivado"
        await ctx.send(
            embed=embeds.success(
                strings.SHOP_TITLE,
                strings.ADMIN_ITEM_TOGGLED.format(item_id=item_id, state=state),
            )
        )

    @shop_group.command(name="seed", description="Crea el catálogo temático inicial.")
    async def shop_seed(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        created = 0
        for name, price, kind, description in SEED_ITEMS:
            item_id = await self.bot.db.create_shop_item(
                guild_id=ctx.guild.id,
                name=name,
                price=price,
                kind=kind,
                description=description,
            )
            if item_id is not None:
                created += 1
        await ctx.send(
            embed=embeds.success(
                strings.SHOP_TITLE,
                strings.ADMIN_SEED_DONE.format(created=created, total=len(SEED_ITEMS)),
            )
        )

    # ---------------------------------------------------------------- economy

    @commands.hybrid_group(name="eco", fallback="audit", description="Gestiona la economía.")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def eco_group(self, ctx: commands.Context, member: discord.Member) -> None:
        assert ctx.guild is not None
        history = await self.bot.db.get_transactions(member.id, ctx.guild.id)
        if not history:
            await ctx.send(embed=embeds.error(strings.ADMIN_AUDIT_EMPTY), ephemeral=True)
            return

        lines = []
        for entry in history:
            when = datetime.fromtimestamp(entry.created_at, UTC).strftime("%d/%m %H:%M")
            sign = "+" if entry.delta >= 0 else ""
            lines.append(f"`{when}` **{sign}{fmt_number(entry.delta)}** · {entry.reason}")
        embed = embeds.base(
            strings.ADMIN_AUDIT_TITLE.format(user=member.display_name), "\n".join(lines)
        )
        await ctx.send(embed=embed, ephemeral=True)

    @eco_group.command(name="give", description="Otorga Fe a un miembro.")
    async def eco_give(
        self, ctx: commands.Context, member: discord.Member, amount: int
    ) -> None:
        await self._adjust(ctx, member, amount)

    @eco_group.command(name="take", description="Retira Fe a un miembro.")
    async def eco_take(
        self, ctx: commands.Context, member: discord.Member, amount: int
    ) -> None:
        await self._adjust(ctx, member, -amount)

    @eco_group.command(name="set", description="Fija el saldo exacto de un miembro.")
    async def eco_set(self, ctx: commands.Context, member: discord.Member, amount: int) -> None:
        assert ctx.guild is not None
        balance = await self.bot.db.set_balance(member.id, ctx.guild.id, max(0, amount))
        await self._report_balance(ctx, member, balance)

    async def _adjust(
        self, ctx: commands.Context, member: discord.Member, delta: int
    ) -> None:
        assert ctx.guild is not None
        balance = await self.bot.db.add_faith(
            member.id, ctx.guild.id, delta, TxReason.ADMIN, ctx.author.id
        )
        if balance < 0:
            balance = await self.bot.db.set_balance(member.id, ctx.guild.id, 0)
        await self._report_balance(ctx, member, balance)

    async def _report_balance(
        self, ctx: commands.Context, member: discord.Member, balance: int
    ) -> None:
        assert ctx.guild is not None
        logger.info(
            "Balance adjusted by admin | guild=%s admin=%s target=%s balance=%s",
            ctx.guild.id,
            ctx.author.id,
            member.id,
            balance,
        )
        await ctx.send(
            embed=embeds.success(
                "⚙️",
                strings.ADMIN_ECO_DONE.format(
                    user=member.mention,
                    balance=fmt_number(balance),
                    currency=config.CURRENCY,
                ),
            )
        )


def _is_integer(value: str) -> bool:
    return value.lstrip("-").isdigit()


def _bot_can_assign(guild: discord.Guild, role: discord.Role) -> bool:
    """A role is sellable only if the bot outranks it and it is not managed."""
    me = guild.me
    if me is None or not me.guild_permissions.manage_roles:
        return False
    return not role.managed and role < me.top_role


async def setup(bot: "KourindouBot") -> None:
    await bot.add_cog(AdminCog(bot))
