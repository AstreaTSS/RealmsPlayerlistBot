import asyncio
import itertools

import discord
from discord.ext import commands

import common.paginator as paginator

# most of this code has been copied from https://github.com/Rapptz/RoboDanny
# or, at least, was copied over
# ill look over commit histories one day to find out where is this from


class HelpPaginator(paginator.Pages):
    def __init__(self, help_command, ctx, entries, *, per_page=4):
        super().__init__(ctx, entries=entries, per_page=per_page)
        self.reaction_emojis.append(
            ("\N{WHITE QUESTION MARK ORNAMENT}", self.show_bot_help)
        )
        self.total = len(entries)
        self.help_command = help_command
        self.prefix = help_command.clean_prefix
        self.is_bot = False

    def get_bot_page(self, page):
        cog, description, commands = self.entries[page - 1]
        self.title = f"{cog} Commands"
        self.description = description
        return commands

    def prepare_embed(self, entries, page, *, first=False):
        self.embed.clear_fields()
        self.embed.description = self.description
        self.embed.title = self.title

        if self.is_bot:
            value = "For more help, join the official support server: https://discord.gg/NSdetwGjpK"
            self.embed.add_field(name="Support", value=value, inline=False)

        self.embed.set_footer(
            text=f'Use "{self.prefix}help command" for more info on a command.'
        )

        for entry in entries:
            signature = f'{entry.qualified_name.replace("_", "-")} {entry.signature}'
            self.embed.add_field(
                name=signature, value=entry.short_doc or "No help given", inline=False
            )

        if self.maximum_pages:
            self.embed.set_author(
                name=f"Page {page}/{self.maximum_pages} ({self.total} commands)"
            )

    async def show_help(self):
        """shows this message"""

        self.embed.title = "Paginator help"
        self.embed.description = "Hello! Welcome to the help page."

        messages = [f"{emoji} {func.__doc__}" for emoji, func in self.reaction_emojis]
        self.embed.clear_fields()
        self.embed.add_field(
            name="What are these reactions for?",
            value="\n".join(messages),
            inline=False,
        )

        self.embed.set_footer(
            text=f"We were on page {self.current_page} before this message."
        )
        await self.message.edit(embed=self.embed)

        async def go_back_to_current_page():
            await asyncio.sleep(30.0)
            await self.show_current_page()

        self.bot.loop.create_task(go_back_to_current_page())

    async def show_bot_help(self):
        """shows how to use the bot"""

        self.embed.title = "Using the bot"
        self.embed.description = "Hello! Welcome to the help page."
        self.embed.clear_fields()

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

        self.embed.add_field(
            name="How do I use this bot?",
            value="Reading the bot signature is pretty simple.",
        )

        for name, value in entries:
            self.embed.add_field(name=name, value=value, inline=False)

        self.embed.set_footer(
            text=f"We were on page {self.current_page} before this message."
        )
        await self.message.edit(embed=self.embed)

        async def go_back_to_current_page():
            await asyncio.sleep(30.0)
            await self.show_current_page()

        self.bot.loop.create_task(go_back_to_current_page())


class PaginatedHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__(
            command_attrs={
                "cooldown": commands.Cooldown(1, 3.0, commands.BucketType.member),
                "help": "Shows help about the bot, a command, or a category",
            }
        )

    async def on_help_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.reply(str(error.original))

    async def command_callback(self, ctx, *, command=None):
        if command != None:
            command = command.replace("-", "_")

        await super().command_callback(ctx, command=command)

    def get_command_signature(self, command):
        parent = command.full_parent_name.replace("_", "-")
        if len(command.aliases) > 0:
            aliases = "|".join(command.aliases)
            fmt = f'[{command.name.replace("_", "-")}|{aliases}]'
            if parent:
                fmt = f"{parent} {fmt}"
            alias = fmt
        else:
            alias = (
                command.name.replace("_", "-")
                if not parent
                else f'{parent} {command.name.replace("_", "-")}'
            )
        return f"{alias} {command.signature}"

    async def send_bot_help(self, mapping):
        def key(c):
            return c.cog_name or "\u200bNo Category"

        bot = self.context.bot
        entries = await self.filter_commands(bot.commands, sort=True, key=key)
        nested_pages = []
        per_page = 9
        total = 0

        for cog, commands in itertools.groupby(entries, key=key):
            commands = sorted(commands, key=lambda c: c.name.replace("_", "-"))
            if len(commands) == 0:
                continue

            total += len(commands)
            actual_cog = bot.get_cog(cog)
            # get the description if it exists (and the cog is valid) or return Empty embed.
            description = (actual_cog and actual_cog.description) or discord.Embed.Empty
            nested_pages.extend(
                (cog, description, commands[i : i + per_page])
                for i in range(0, len(commands), per_page)
            )

        # a value of 1 forces the pagination session
        pages = HelpPaginator(self, self.context, nested_pages, per_page=1)

        # swap the get_page implementation to work with our nested pages.
        pages.get_page = pages.get_bot_page
        pages.is_bot = True
        pages.total = total
        await pages.paginate()

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(
            cog.get_commands(), sort=True, key=lambda c: c.name.replace("_", "-")
        )
        pages = HelpPaginator(self, self.context, entries)
        pages.title = f"{cog.qualified_name} Commands"
        pages.description = cog.description

        await pages.paginate()

    def common_command_formatting(self, page_or_embed, command):
        page_or_embed.title = self.get_command_signature(command)
        if command.description:
            page_or_embed.description = f"{command.description}\n\n{command.help}"
        else:
            page_or_embed.description = command.help or "No help found..."

    async def send_command_help(self, command):
        # No pagination necessary for a single command.
        embed = discord.Embed(colour=self.context.bot.color)
        self.common_command_formatting(embed, command)
        await self.context.reply(embed=embed)

    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        pages = HelpPaginator(self, self.context, entries)
        self.common_command_formatting(pages, group)

        await pages.paginate()

    async def command_not_found(self, string: str):
        actual_str = string.replace("_", "-")
        return await super().command_not_found(actual_str)

    async def subcommand_not_found(self, command, string: str):
        qualified_name = command.qualified_name.replace("_", "-")

        if isinstance(command, commands.Group) and len(command.all_commands) > 0:
            actual_str = string.replace("_", "-")
            return f'Command "{qualified_name}" has no subcommand named {actual_str}'

        return f'Command "{qualified_name}" has no subcommands.'
