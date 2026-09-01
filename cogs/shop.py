"""Kourindou shop: interactive catalogue, purchases and inventory."""

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

import config
import strings
from core import embeds
from core.text import fmt_number
from database.models import ItemKind, PurchaseResult, ShopItem

if TYPE_CHECKING:
    from main import KourindouBot

logger = logging.getLogger(__name__)

SELECT_LIMIT = 25


async def execute_purchase(
    bot: "KourindouBot", member: discord.Member, item: ShopItem
) -> PurchaseResult:
    """Charge the item and apply its side effect, refunding if the effect fails."""
    result = await bot.db.purchase_item(member.id, member.guild.id, item)
    if result is not PurchaseResult.OK:
        return result

    if item.kind == ItemKind.ROLE.value:
        role = _resolve_role(member.guild, item.payload)
        if role is None:
            logger.warning(
                "Shop item points to a missing role | guild=%s item=%s payload=%r",
                member.guild.id,
                item.item_id,
                item.payload,
            )
            await bot.db.refund_purchase(member.id, member.guild.id, item)
            return PurchaseResult.ROLE_FAILED
        try:
            await member.add_roles(role, reason="Compra en la Tienda Kourindou")
        except discord.Forbidden:
            logger.warning(
                "Role assignment denied, check bot hierarchy | guild=%s role=%s user=%s",
                member.guild.id,
                role.id,
                member.id,
            )
            await bot.db.refund_purchase(member.id, member.guild.id, item)
            return PurchaseResult.ROLE_FAILED
        except discord.HTTPException:
            logger.exception(
                "Discord API failure assigning role | guild=%s role=%s user=%s",
                member.guild.id,
                role.id,
                member.id,
            )
            await bot.db.refund_purchase(member.id, member.guild.id, item)
            return PurchaseResult.ROLE_FAILED

    return PurchaseResult.OK


def _resolve_role(guild: discord.Guild, payload: str | None) -> discord.Role | None:
    if not payload or not payload.isdigit():
        return None
    return guild.get_role(int(payload))


def purchase_message(result: PurchaseResult, item: ShopItem, missing: int) -> str:
    if result is PurchaseResult.OK:
        return strings.SHOP_PURCHASE_OK.format(name=item.name)
    if result is PurchaseResult.INSUFFICIENT_FUNDS:
        return strings.SHOP_INSUFFICIENT.format(
            missing=fmt_number(missing), currency=config.CURRENCY
        )
    if result is PurchaseResult.ALREADY_OWNED:
        return strings.SHOP_ALREADY_OWNED.format(name=item.name)
    if result is PurchaseResult.OUT_OF_STOCK:
        return strings.SHOP_OUT_OF_STOCK.format(name=item.name)
    if result is PurchaseResult.ROLE_FAILED:
        return strings.SHOP_ROLE_FAILED
    return strings.SHOP_UNAVAILABLE


class ConfirmView(discord.ui.View):
    """Second step of a purchase. Lives only inside an ephemeral message."""

    def __init__(self, author_id: int) -> None:
        super().__init__(timeout=config.SHOP_VIEW_TIMEOUT)
        self.author_id = author_id
        self.confirmed: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(strings.NOT_YOUR_MENU, ephemeral=True)
            return False
        return True

    @discord.ui.button(label=strings.SHOP_BUY, style=discord.ButtonStyle.success, emoji="🪙")
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label=strings.SHOP_CANCEL, style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.confirmed = False
        await interaction.response.defer()
        self.stop()


class CategorySelect(discord.ui.Select):
    def __init__(self, kinds: list[str], current: str) -> None:
        options = [
            discord.SelectOption(
                label=strings.SHOP_KIND_LABELS.get(kind, kind),
                value=kind,
                default=kind == current,
            )
            for kind in kinds
        ]
        super().__init__(placeholder=strings.SHOP_CATEGORY_PLACEHOLDER, options=options, row=0)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ShopView = self.view  # type: ignore[assignment]
        view.select_category(self.values[0])
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class ItemSelect(discord.ui.Select):
    def __init__(self, items: list[ShopItem], selected_id: int | None) -> None:
        options = [
            discord.SelectOption(
                label=item.name[:100],
                value=str(item.item_id),
                description=f"{fmt_number(item.price)} {config.CURRENCY_NAME}"[:100],
                default=item.item_id == selected_id,
            )
            for item in items
        ]
        super().__init__(
            placeholder=strings.SHOP_SELECT_PLACEHOLDER,
            options=options or [discord.SelectOption(label="—", value="0")],
            disabled=not options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ShopView = self.view  # type: ignore[assignment]
        view.select_item(int(self.values[0]))
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class BuyButton(discord.ui.Button):
    def __init__(self, disabled: bool) -> None:
        super().__init__(
            label=strings.SHOP_BUY,
            style=discord.ButtonStyle.success,
            emoji="🪙",
            disabled=disabled,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ShopView = self.view  # type: ignore[assignment]
        item = view.selected
        if item is None:
            return

        confirm = ConfirmView(view.author.id)
        await interaction.response.send_message(
            embed=embeds.base(
                strings.SHOP_TITLE,
                strings.SHOP_CONFIRM.format(
                    name=item.name, price=fmt_number(item.price), currency=config.CURRENCY
                ),
            ),
            view=confirm,
            ephemeral=True,
        )
        await confirm.wait()
        if not confirm.confirmed:
            await interaction.edit_original_response(
                embed=embeds.error(strings.SHOP_CANCELLED), view=None
            )
            return

        # Re-read the catalogue: price or availability may have changed while the
        # confirmation dialog was open.
        fresh = await view.cog.bot.db.get_shop_item(item.item_id)
        if fresh is None:
            await interaction.edit_original_response(
                embed=embeds.error(strings.SHOP_UNAVAILABLE), view=None
            )
            return

        result = await execute_purchase(view.cog.bot, view.author, fresh)
        balance = await view.cog.bot.db.get_balance(view.author.id, view.author.guild.id)
        message = purchase_message(result, fresh, max(0, fresh.price - balance))
        embed = (
            embeds.success(strings.SHOP_TITLE, message)
            if result is PurchaseResult.OK
            else embeds.error(message)
        )
        await interaction.edit_original_response(embed=embed, view=None)

        view.balance = balance
        try:
            if view.message is not None:
                await view.message.edit(embed=view.build_embed(), view=view)
        except discord.HTTPException:
            logger.debug("Could not refresh the shop message after a purchase")


class ShopView(discord.ui.View):
    def __init__(
        self, cog: "ShopCog", author: discord.Member, items: list[ShopItem], balance: int
    ) -> None:
        super().__init__(timeout=config.SHOP_VIEW_TIMEOUT)
        self.cog = cog
        self.author = author
        self.items = items
        self.balance = balance
        self.message: discord.Message | None = None
        self.selected: ShopItem | None = None
        self.kinds = sorted({item.kind for item in items})
        self.current_kind = self.kinds[0]
        self._rebuild()

    def _visible_items(self) -> list[ShopItem]:
        return [item for item in self.items if item.kind == self.current_kind]

    def _rebuild(self) -> None:
        self.clear_items()
        if len(self.kinds) > 1:
            self.add_item(CategorySelect(self.kinds, self.current_kind))
        self.add_item(
            ItemSelect(
                self._visible_items()[:SELECT_LIMIT],
                self.selected.item_id if self.selected else None,
            )
        )
        self.add_item(BuyButton(disabled=self.selected is None))

    def select_category(self, kind: str) -> None:
        self.current_kind = kind
        self.selected = None
        self._rebuild()

    def select_item(self, item_id: int) -> None:
        self.selected = next((item for item in self.items if item.item_id == item_id), None)
        self._rebuild()

    def build_embed(self) -> discord.Embed:
        if self.selected is None:
            visible = self._visible_items()
            lines = [
                f"**{item.name}** — {fmt_number(item.price)} {config.CURRENCY}"
                + (f"\n*{item.description}*" if item.description else "")
                for item in visible[:SELECT_LIMIT]
            ]
            embed = embeds.base(
                strings.SHOP_TITLE, strings.SHOP_DESCRIPTION + "\n\n" + "\n".join(lines)
            )
            if len(visible) > SELECT_LIMIT:
                embed.add_field(
                    name="Catálogo",
                    value=strings.SHOP_TRUNCATED.format(shown=SELECT_LIMIT, total=len(visible)),
                    inline=False,
                )
        else:
            item = self.selected
            embed = embeds.base(f"🏮 {item.name}", item.description or "")
            embed.add_field(
                name="Precio",
                value=strings.SHOP_ITEM_PRICE.format(
                    price=fmt_number(item.price), currency=config.CURRENCY
                ),
                inline=True,
            )
            if item.stock is not None:
                embed.add_field(
                    name="Existencias",
                    value=strings.SHOP_ITEM_STOCK.format(stock=fmt_number(item.stock)),
                    inline=True,
                )
        embed.set_footer(
            text=strings.SHOP_FOOTER.format(
                balance=fmt_number(self.balance), currency=config.CURRENCY
            )
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(strings.NOT_YOUR_MENU, ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True  # type: ignore[attr-defined]
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                logger.debug("Shop view message was gone on timeout")


class ShopCog(commands.Cog, name="Tienda"):
    def __init__(self, bot: "KourindouBot") -> None:
        self.bot = bot

    @commands.hybrid_command(name="shop", description="Abre la Tienda Kourindou.")
    @commands.guild_only()
    async def shop(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        items = await self.bot.db.list_shop_items(ctx.guild.id)
        if not items:
            await ctx.send(embed=embeds.error(strings.SHOP_EMPTY), ephemeral=True)
            return

        balance = await self.bot.db.get_balance(ctx.author.id, ctx.guild.id)
        member = ctx.guild.get_member(ctx.author.id)
        if member is None:
            await ctx.send(embed=embeds.error(strings.ERROR_GUILD_ONLY), ephemeral=True)
            return

        view = ShopView(self, member, items, balance)
        view.message = await ctx.send(embed=view.build_embed(), view=view)

    @commands.hybrid_command(name="inventory", description="Muestra los artículos que posees.")
    @commands.guild_only()
    async def inventory(
        self, ctx: commands.Context, member: discord.Member | None = None
    ) -> None:
        assert ctx.guild is not None
        target = member or ctx.author
        entries = await self.bot.db.get_inventory(target.id, ctx.guild.id)
        if not entries:
            await ctx.send(embed=embeds.error(strings.INVENTORY_EMPTY), ephemeral=True)
            return

        grouped: dict[str, list[str]] = {}
        for entry in entries:
            label = strings.SHOP_KIND_LABELS.get(entry.kind, entry.kind)
            grouped.setdefault(label, []).append(entry.name)

        embed = embeds.base(strings.INVENTORY_TITLE.format(user=target.display_name))
        for label, names in grouped.items():
            listing = "\n".join(f"• {name}" for name in names)
            embed.add_field(name=label, value=listing, inline=False)
        await ctx.send(embed=embeds.with_author(embed, target))


async def setup(bot: "KourindouBot") -> None:
    await bot.add_cog(ShopCog(bot))
