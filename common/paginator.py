import asyncio
import typing
import uuid

import attr
import nextcord
from nextcord.ext import commands
from nextcord.ext.commands import Paginator as CommandPaginator

# most of this code has been copied from https://github.com/Rapptz/RoboDanny


def gen_uuid():
    return str(uuid.uuid4())


@attr.s()
class ReactionEmoji:
    """An easy to use wrapper around reactions."""

    emoji: str = attr.ib()
    row: int = attr.ib()
    function: typing.Callable = attr.ib()
    uuid: str = attr.ib(factory=gen_uuid)

    def to_button(self):
        button = nextcord.ui.Button(
            style=nextcord.ButtonStyle.primary,
            emoji=self.emoji,
            custom_id=self.uuid,
            row=self.row,
        )
        button.callback = self.function  # very dirty
        return button


def generate_view(
    emojis: typing.List[ReactionEmoji],
    author: typing.Union[nextcord.Member, nextcord.User],
):
    class PaginatorView(nextcord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)

        async def interaction_check(self, interaction: nextcord.Interaction) -> bool:
            return interaction.user.id == author.id

        async def on_timeout(self):
            try:
                self.stop()
            except TypeError:
                pass  # ??????

    view = PaginatorView()

    for emoji in emojis:
        view.add_item(emoji.to_button())

    return view


class CannotPaginate(Exception):
    pass


class Pages:
    """Implements a paginator that queries the user for the
    pagination interface.
    Pages are 1-index based, not 0-index based.
    If the user does not reply within 2 minutes then the pagination
    interface exits automatically.
    Parameters
    ------------
    ctx: Context
        The context of the command.
    entries: List[str]
        A list of entries to paginate.
    per_page: int
        How many entries show up per page.
    show_entry_count: bool
        Whether to show an entry count in the footer.
    Attributes
    -----------
    embed: nextcord.Embed
        The embed object that is being used to send pagination info.
        Feel free to modify this externally. Only the description,
        footer fields, and colour are internally modified.
    permissions: nextcord.Permissions
        Our permissions for the channel.
    """

    def __init__(
        self, ctx: commands.Context, *, entries, per_page=12, show_entry_count=True
    ):
        self.bot = ctx.bot
        self.context = ctx
        self.entries = entries
        self.message = ctx.message
        self.channel = ctx.channel
        self.author = ctx.author
        self.per_page = per_page
        pages, left_over = divmod(len(self.entries), self.per_page)
        if left_over:
            pages += 1
        self.maximum_pages = pages
        self.embed = nextcord.Embed(colour=ctx.bot.color)
        self.paginating = len(entries) > per_page
        self.show_entry_count = show_entry_count
        self.reaction_emojis = [
            ReactionEmoji("⏮️", 0, self.first_page),
            ReactionEmoji("◀️", 0, self.previous_page),
            ReactionEmoji("▶️", 0, self.next_page),
            ReactionEmoji("⏭️", 0, self.last_page),
            ReactionEmoji("🔢", 1, self.numbered_page),
            ReactionEmoji("⏹️", 1, self.stop_pages),
            ReactionEmoji("ℹ️", 1, self.show_help),
        ]

        if ctx.guild is not None:
            self.permissions = self.channel.permissions_for(ctx.guild.me)
        else:
            self.permissions = self.channel.permissions_for(ctx.bot.user)

        if not self.permissions.embed_links:
            raise CannotPaginate("Bot does not have embed links permission.")

        if not self.permissions.send_messages:
            raise CannotPaginate("Bot cannot send messages.")

        if self.paginating:
            # verify we can actually use the pagination session
            if not self.permissions.add_reactions:
                raise CannotPaginate("Bot does not have add reactions permission.")

            if not self.permissions.read_message_history:
                raise CannotPaginate(
                    "Bot does not have Read Message History permission."
                )

    def get_page(self, page):
        base = (page - 1) * self.per_page
        return self.entries[base : base + self.per_page]

    def get_content(self, entries, page, *, first=False):
        return None

    def get_embed(self, entries, page, *, first=False):
        self.prepare_embed(entries, page, first=first)
        return self.embed

    def prepare_embed(self, entries, page, *, first=False):
        p = [
            f"{index}. {entry}"
            for index, entry in enumerate(entries, 1 + ((page - 1) * self.per_page))
        ]

        if self.maximum_pages > 1:
            if self.show_entry_count:
                text = f"Page {page}/{self.maximum_pages} ({len(self.entries)} entries)"
            else:
                text = f"Page {page}/{self.maximum_pages}"

            self.embed.set_footer(text=text)

        if self.paginating and first:
            p.append("")
            p.append("Confused? Use the \N{INFORMATION SOURCE} button for more info.")

        self.embed.description = "\n".join(p)

    async def show_page(
        self, page, *, interaction: typing.Optional[nextcord.Interaction], first=False
    ):
        self.current_page = page
        entries = self.get_page(page)
        content = self.get_content(entries, page, first=first)
        embed = self.get_embed(entries, page, first=first)

        if not self.paginating:
            return await self.context.reply(content=content, embed=embed)

        if not first:
            return await interaction.response.edit_message(content=content, embed=embed)

        self.message = await self.context.reply(
            content=content,
            embed=embed,
            view=generate_view(self.reaction_emojis, self.author),
        )

    async def checked_show_page(self, page, inter: nextcord.Interaction):
        if page != 0 and page <= self.maximum_pages:
            await self.show_page(page, interaction=inter)

    async def first_page(self, inter: nextcord.Interaction):
        """goes to the first page"""
        await self.show_page(1, interaction=inter)

    async def last_page(self, inter: nextcord.Interaction):
        """goes to the last page"""
        await self.show_page(self.maximum_pages, interaction=inter)

    async def next_page(self, inter: nextcord.Interaction):
        """goes to the next page"""
        await self.checked_show_page(self.current_page + 1, inter)

    async def previous_page(self, inter: nextcord.Interaction):
        """goes to the previous page"""
        await self.checked_show_page(self.current_page - 1, inter)

    async def show_current_page(self, inter: nextcord.Interaction):
        if self.paginating:
            await self.show_page(self.current_page, interaction=inter)

    async def numbered_page(self, inter: nextcord.Interaction):
        """lets you type a page number to go to"""
        to_delete = []
        to_delete.append(await self.channel.send("What page do you want to go to?"))

        def message_check(m):
            return (
                m.author == self.author
                and self.channel == m.channel
                and m.content.isdigit()
            )

        try:
            msg = await self.bot.wait_for("message", check=message_check, timeout=30.0)
        except asyncio.TimeoutError:
            to_delete.append(await self.channel.send("Took too long."))
            await asyncio.sleep(5)
        else:
            page = int(msg.content)
            to_delete.append(msg)
            if page != 0 and page <= self.maximum_pages:
                await self.show_page(page, interaction=inter)
            else:
                to_delete.append(
                    await self.channel.send(
                        f"Invalid page given. ({page}/{self.maximum_pages})"
                    )
                )
                await asyncio.sleep(5)

        try:
            await self.channel.delete_messages(to_delete)
        except Exception:
            pass

    async def show_help(self, inter: nextcord.Interaction):
        """shows this message"""
        messages = ["Welcome to the interactive paginator!\n"]
        messages.append(
            "This interactively allows you to see pages of text by navigating with "
            "reactions. They are as follows:\n"
        )

        for reaction in self.reaction_emojis:
            messages.append(f"{reaction.emoji} {reaction.function.__doc__}")

        embed = self.embed.copy()
        embed.clear_fields()
        embed.description = "\n".join(messages)
        embed.set_footer(
            text=f"We were on page {self.current_page} before this message."
        )
        await inter.response.edit_message(content=None, embed=embed)

        async def go_back_to_current_page():
            await asyncio.sleep(60.0)
            await self.show_current_page(inter)

        self.bot.loop.create_task(go_back_to_current_page())

    async def stop_pages(self, inter: nextcord.Interaction):
        """stops the interactive pagination session"""
        try:
            await inter.response.edit_message(
                content="The help command has stopped running.", embed=None, view=None,
            )
        except:
            pass
        finally:
            self.paginating = False

    async def paginate(self):
        """Actually paginate the entries and run the interactive loop if necessary."""
        first_page = self.show_page(1, interaction=None, first=True)
        if not self.paginating:
            await first_page
        else:
            # allow us to react to reactions right away if we're paginating
            self.bot.loop.create_task(first_page)


class FieldPages(Pages):
    """Similar to Pages except entries should be a list of
    tuples having (key, value) to show as embed fields instead.
    """

    def prepare_embed(self, entries, page, *, first=False):
        self.embed.clear_fields()
        self.embed.description = nextcord.Embed.Empty

        for key, value in entries:
            self.embed.add_field(name=key, value=value, inline=False)

        if self.maximum_pages > 1:
            if self.show_entry_count:
                text = f"Page {page}/{self.maximum_pages} ({len(self.entries)} entries)"
            else:
                text = f"Page {page}/{self.maximum_pages}"

            self.embed.set_footer(text=text)


class TextPages(Pages):
    """Uses a commands.Paginator internally to paginate some text."""

    def __init__(self, ctx, text, *, prefix="```", suffix="```", max_size=2000):
        paginator = CommandPaginator(
            prefix=prefix, suffix=suffix, max_size=max_size - 200
        )
        for line in text.split("\n"):
            paginator.add_line(line)

        super().__init__(
            ctx, entries=paginator.pages, per_page=1, show_entry_count=False
        )

    def get_page(self, page):
        return self.entries[page - 1]

    def get_embed(self, entries, page, *, first=False):
        return None

    def get_content(self, entry, page, *, first=False):
        if self.maximum_pages > 1:
            return f"{entry}\nPage {page}/{self.maximum_pages}"
        return entry
