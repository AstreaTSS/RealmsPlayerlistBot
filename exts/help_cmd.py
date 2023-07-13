import importlib
import typing

import interactions as ipy
import tansy

import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.utils as utils


class HelpCMD(utils.Extension):
    """The cog that handles the help command."""

    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.name = "Help Category"
        self.bot: utils.RealmBotBase = bot

    async def _check_wrapper(
        self, ctx: ipy.BaseContext, check: typing.Callable
    ) -> bool:
        """A wrapper to ignore errors by checks."""
        try:
            return await check(ctx)
        except Exception:
            return False

    async def _custom_can_run(
        self, ctx: ipy.BaseInteractionContext, cmd: help_tools.MiniCommand
    ) -> bool:
        """
        Determines if this command can be run, but ignores cooldowns and concurrency.
        """

        slash_cmd = cmd.slash_command

        if not slash_cmd.get_cmd_id(int(ctx.guild_id)):
            return False

        if not self.bot.slash_perms_cache.get(int(ctx.guild_id)):
            return False

        if not self.bot.slash_perms_cache[int(ctx.guild_id)][
            int(slash_cmd.get_cmd_id(int(ctx.guild_id)))
        ].has_permission_ctx(ctx):
            return False

        if cmd.subcommands:
            return True

        if not slash_cmd.enabled:
            return False

        for check in slash_cmd.checks:
            if not await self._check_wrapper(ctx, check):
                return False

        if slash_cmd.extension and slash_cmd.extension.extension_checks:
            for check in slash_cmd.extension.extension_checks:
                if not await self._check_wrapper(ctx, check):
                    return False

        return True

    async def extract_commands(
        self, ctx: ipy.AutocompleteContext, argument: typing.Optional[str]
    ) -> tuple[str, ...]:
        cmds = help_tools.get_mini_commands_for_scope(self.bot, int(ctx.guild_id))

        runnable_cmds = [v for v in cmds.values() if await self._custom_can_run(ctx, v)]
        valid_exts = {c.extension.name for c in runnable_cmds if c.extension}
        sorted_exts = {e.lower(): e for e in sorted(valid_exts)}
        resolved_names = {
            c.resolved_name.lower(): c.resolved_name
            for c in sorted(runnable_cmds, key=lambda c: c.resolved_name)
        }

        combined = sorted_exts | resolved_names

        if not argument:
            return tuple(combined.values())[:25]

        queried_cmds: list[list[str]] = fuzzy.extract_from_list(
            argument=argument.lower(),
            list_of_items=tuple(combined.keys()),
            processors=[lambda x: x.lower()],
            score_cutoff=0.7,
        )
        return tuple(combined[c[0]] for c in queried_cmds)[:25]

    async def get_multi_command_embeds(
        self,
        ctx: utils.RealmContext,
        commands: list[help_tools.MiniCommand],
        name: str,
        description: typing.Optional[str],
    ) -> list[ipy.Embed]:
        embeds: list[ipy.Embed] = []

        commands = [c for c in commands if await self._custom_can_run(ctx, c)]
        if not commands:
            return []

        chunks = [commands[x : x + 9] for x in range(0, len(commands), 9)]
        multiple_embeds = len(chunks) > 1

        for index, chunk in enumerate(chunks):
            embed = ipy.Embed(description=description, color=ctx.bot.color)

            embed.add_field(
                name="Support",
                value=(
                    "For more help, join the official support server:"
                    " https://discord.gg/NSdetwGjpK"
                ),
                inline=False,
            )
            embed.set_footer(text='Use "/help command" for more info on a command.')

            embed.title = f"{name} - Page {index + 1}" if multiple_embeds else name
            for cmd in chunk:
                signature = f"{cmd.resolved_name} {cmd.signature}".strip()
                embed.add_field(
                    name=signature,
                    value=cmd.brief_description,
                    inline=False,
                )

            embeds.append(embed)

        return embeds

    async def get_ext_cmd_embeds(
        self,
        ctx: utils.RealmContext,
        cmds: dict[str, help_tools.MiniCommand],
        ext: ipy.Extension,
    ) -> list[ipy.Embed]:
        slash_cmds = [
            c
            for c in cmds.values()
            if c.extension == ext and " " not in c.resolved_name
        ]
        slash_cmds.sort(key=lambda c: c.resolved_name)

        if not slash_cmds:
            return []

        name = f"{ext.name} Commands"
        return await self.get_multi_command_embeds(
            ctx, slash_cmds, name, ext.description
        )

    async def get_all_cmd_embeds(
        self,
        ctx: utils.RealmContext,
        cmds: dict[str, help_tools.MiniCommand],
        bot: utils.RealmBotBase,
    ) -> list[ipy.Embed]:
        embeds: list[ipy.Embed] = []

        for ext in bot.ext.values():
            ext_cmd_embeds = await self.get_ext_cmd_embeds(ctx, cmds, ext)
            if ext_cmd_embeds:
                embeds.extend(ext_cmd_embeds)

        return embeds

    async def get_command_embeds(
        self, ctx: utils.RealmContext, command: help_tools.MiniCommand
    ) -> list[ipy.Embed]:
        if command.subcommands:
            return await self.get_multi_command_embeds(
                ctx, command.view_subcommands, command.name, command.description
            )

        signature = f"{command.resolved_name} {command.signature}"
        return [
            ipy.Embed(
                title=signature,
                description=command.description,
                color=ctx.bot.color,
            )
        ]

    @tansy.slash_command(
        name="help",
        description="Shows help about the bot, a command, or a category.",
        dm_permission=False,
    )
    async def help_cmd(
        self,
        ctx: utils.RealmContext,
        query: typing.Optional[str] = tansy.Option(
            "The query to search for. Can be a command or a category.",
            autocomplete=True,
            default=None,
        ),
    ) -> None:
        """Shows help about the bot, a command, or a category."""
        embeds: list[ipy.Embed] = []

        if not self.bot.slash_perms_cache[int(ctx.guild_id)]:
            await help_tools.process_bulk_slash_perms(self.bot, int(ctx.guild_id))

        cmds = help_tools.get_mini_commands_for_scope(self.bot, int(ctx.guild_id))

        if not query:
            embeds = await self.get_all_cmd_embeds(ctx, cmds, self.bot)
        elif (command := cmds.get(query.lower())) and await self._custom_can_run(
            ctx, command
        ):
            embeds = await self.get_command_embeds(ctx, command)
        else:
            ext: typing.Optional[ipy.Extension] = next(
                (s for s in self.bot.ext.values() if s.name.lower() == query.lower()),
                None,
            )
            if not ext:
                raise ipy.errors.BadArgument(
                    f"No valid command called `{query}` found."
                )

            embeds = await self.get_ext_cmd_embeds(ctx, cmds, ext)
            if not embeds:
                raise ipy.errors.BadArgument(
                    f"There are no valid commands for `{ext.name}`."
                )

        if not embeds:
            raise ipy.errors.BadArgument(f"No valid command called `{query}` found.")

        if len(embeds) == 1:
            # pointless to do a paginator here
            await ctx.send(embeds=embeds)
            return

        pag = help_tools.HelpPaginator.create_from_embeds(self.bot, *embeds, timeout=60)
        await pag.send(ctx)

    @help_cmd.autocomplete("query")
    async def query_autocomplete(
        self,
        ctx: utils.RealmAutocompleteContext,
    ) -> None:
        query = ctx.kwargs.get("query")

        if not self.bot.slash_perms_cache[int(ctx.guild_id)]:
            await help_tools.process_bulk_slash_perms(self.bot, int(ctx.guild_id))

        commands = await self.extract_commands(ctx, query)
        await ctx.send([{"name": c, "value": c} for c in commands])


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(help_tools)
    HelpCMD(bot)
