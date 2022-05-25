import asyncio
import typing

import attrs
import naff
from naff.ext import paginators
from naff.models.discord.emoji import process_emoji


async def callback(ctx: naff.ComponentContext):
    """Shows how to use the bot"""

    embed = naff.Embed(color=ctx.bot.color)

    embed.title = "Using this command"
    embed.description = "Hello! Welcome to the help page."

    entries = (
        ("<argument>", "This means the argument is __**required**__."),
        ("[argument]", "This means the argument is __**optional**__."),
        ("[A|B]", "This means that it can be __**either A or B**__."),
        (
            "[argument...]",
            "This means you can have multiple arguments.\n"
            "Now that you know the basics, it should be noted that...\n"
            "__**You do not type in the brackets!**__",
        ),
    )

    embed.add_field(
        name="How do I use this bot?",
        value="Reading the bot signature is pretty simple.",
    )

    for name, value in entries:
        embed.add_field(name=name, value=value, inline=False)

    await ctx.send(embed=embed, ephemeral=True)


@naff.utils.define(kw_only=False, auto_detect=True)
class HelpPaginator(paginators.Paginator):
    callback: typing.Callable[..., typing.Coroutine] = attrs.field(default=callback)
    """A coroutine to call should the select button be pressed"""
    wrong_user_message: str = attrs.field(
        default="You are not allowed to use this paginator."
    )
    """The message to be sent when the wrong user uses this paginator."""

    callback_button_emoji: typing.Optional[
        typing.Union["naff.PartialEmoji", dict, str]
    ] = attrs.field(default="❔", metadata=naff.utils.export_converter(process_emoji))
    """The emoji to use for the callback button."""
    show_callback_button: bool = attrs.field(default=True)
    """Show a button which will call the `callback`"""
    show_select_menu: bool = attrs.field(default=True)
    """Should a select menu be shown for navigation"""

    def create_components(self, disable=False):
        rows = super().create_components()

        if self.show_select_menu:
            current = self.pages[self.page_index]
            rows[0].components[0] = naff.Select(
                [
                    naff.SelectOption(
                        f"{i+1}:"
                        f" {p.get_summary if isinstance(p, paginators.Page) else p.title}",
                        str(i),
                    )
                    for i, p in enumerate(self.pages)
                ],
                custom_id=f"{self._uuid}|select",
                placeholder=(
                    f"{self.page_index+1}:"
                    f" {current.get_summary if isinstance(current, paginators.Page) else current.title}"
                ),
                max_values=1,
                disabled=disable,
            )

        return rows

    def to_dict(self) -> dict:
        """Convert this paginator into a dictionary for sending."""
        page = self.pages[self.page_index]

        if isinstance(page, paginators.Page):
            page = page.to_embed()
            if not page.title and self.default_title:
                page.title = self.default_title
        if not (page.author and page.author.name):
            page.set_author(name=f"Page {self.page_index+1}/{len(self.pages)}")
        if not page.color:
            page.color = self.default_color

        return {
            "embeds": [page.to_dict()],
            "components": [c.to_dict() for c in self.create_components()],
        }

    async def send(self, ctx: naff.PrefixedContext) -> naff.Message:
        """
        Send this paginator.
        Args:
            ctx: The context to send this paginator with
        Returns:
            The resulting message
        """
        self._message = await ctx.reply(**self.to_dict())
        self._author_id = ctx.author.id

        if self.timeout_interval > 1:
            self._timeout_task = paginators.Timeout(self)
            asyncio.create_task(self._timeout_task())

        return self._message
