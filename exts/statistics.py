"""
Copyright 2020-2025 AstreaTSS.
This file is part of the Realms Playerlist Bot.

The Realms Playerlist Bot is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The Realms Playerlist Bot is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with the Realms
Playerlist Bot. If not, see <https://www.gnu.org/licenses/>.
"""

import datetime
import importlib
import typing

import humanize
import interactions as ipy
import tansy
from tortoise.expressions import Q

import common.classes as cclasses
import common.fuzzy as fuzzy
import common.graph_template as graph_template
import common.help_tools as help_tools
import common.models as models
import common.playerlist_utils as pl_utils
import common.stats_utils as stats_utils
import common.utils as utils


class LeaderboardKwargs(typing.TypedDict, total=False):
    autorunner: bool


class PlaytimeReturn(typing.NamedTuple):
    total_playtime: float
    period_str: str
    length_to_use: int


def amazing_modal_error_handler[T: ipy.const.AsyncCallable](func: T) -> T:
    async def wrapper(
        self: typing.Any,
        unknown: ipy.events.ModalCompletion | ipy.ModalContext,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        ctx = (
            unknown.ctx if isinstance(unknown, ipy.events.ModalCompletion) else unknown
        )

        try:
            await func(self, unknown, *args, **kwargs)
        except ipy.errors.BadArgument as e:
            await ctx.send(embeds=utils.error_embed_generate(str(e)), ephemeral=True)
        except Exception as e:
            await utils.error_handle(e, ctx=ctx)

    return wrapper  # type: ignore


def period_resolver(period: int) -> str:
    match period:
        case 1:
            period_str = "24 hours"
        case 7:
            period_str = "1 week"
        case 14:
            period_str = "2 weeks"
        case _:
            period_str = f"{period} days"
    return period_str


class Statistics(utils.Extension):
    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.name = "Statistics"

    async def make_unsummary_single_graph(
        self,
        ctx: utils.RealmContext,
        period: str,
        unformated_title: str,
        *,
        individual: bool = False,
        gamertag: typing.Optional[str] = None,
        filter_kwargs: dict[str, typing.Any] | None = None,
    ) -> None:
        config = await ctx.fetch_config()
        now = datetime.datetime.now(datetime.UTC)

        returned_data = await stats_utils.process_unsummary(
            ctx,
            now,
            period,
            unformated_title,
            indivdual=individual,
        )
        time_data, datetimes_used = await stats_utils.process_single_graph_data(
            config,
            min_datetime=returned_data.min_datetime,
            now=now,
            func_to_use=returned_data.func_to_use,
            gamertag=gamertag,
            filter_kwargs=filter_kwargs,
        )
        graph = stats_utils.create_single_graph(
            ctx,
            title=returned_data.formatted_title,
            bottom_label=returned_data.bottom_label,
            time_data=time_data,
            localizations=returned_data.localizations,
            **returned_data.template_kwargs,
        )
        await stats_utils.send_graph(
            ctx,
            graph=graph,
            now=now,
            title=returned_data.formatted_title,
            min_datetime=returned_data.min_datetime,
            datetimes_used=datetimes_used,
        )

    async def make_summary_single_graph(
        self,
        ctx: utils.RealmContext,
        summarize_by: str,
        unformated_title: str,
        *,
        gamertag: typing.Optional[str] = None,
        filter_kwargs: dict[str, typing.Any] | None = None,
    ) -> None:
        config = await ctx.fetch_config()
        now = datetime.datetime.now(datetime.UTC)

        returned_data = await stats_utils.process_summary(
            ctx, now, summarize_by, unformated_title
        )
        time_data, datetimes_used = await stats_utils.process_single_graph_data(
            config,
            min_datetime=returned_data.min_datetime,
            now=now,
            func_to_use=returned_data.func_to_use,
            gamertag=gamertag,
            filter_kwargs=filter_kwargs,
        )
        graph = stats_utils.create_single_graph(
            ctx,
            title=returned_data.formatted_title,
            bottom_label=returned_data.bottom_label,
            time_data=time_data,
            localizations=returned_data.localizations,
            max_value=None,
        )
        await stats_utils.send_graph(
            ctx,
            graph=graph,
            now=now,
            title=returned_data.formatted_title,
            min_datetime=returned_data.min_datetime,
            datetimes_used=datetimes_used,
        )

    graph = tansy.SlashCommand(
        name="graph",
        description="Produces various graphs about playtime on the Realm.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @graph.subcommand(
        sub_cmd_name="realm",
        sub_cmd_description=(
            "Produces a graph of the Realm's playtime over a specifed period as a"
            " graph."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(pl_utils.has_linked_realm)
    async def graph_realm(
        self,
        ctx: utils.RealmContext,
        period: str = tansy.Option(
            "The period to graph by. Periods larger than 7 days requires a vote or"
            " Premium.",
            choices=stats_utils.GATED_PERIOD_TO_GRAPH,
        ),
    ) -> None:
        await self.make_unsummary_single_graph(
            ctx, period, "Playtime on the Realm over the last {days_humanized}"
        )

    @graph.subcommand(
        sub_cmd_name="realm-summary",
        sub_cmd_description=(
            "Summarizes the Realm over a specified period, by a specified interval."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(pl_utils.has_linked_realm)
    async def graph_realm_summary(
        self,
        ctx: utils.RealmContext,
        summarize_by: str = tansy.Option(
            "What to summarize by. Periods larger than 7 days requires a vote or"
            " Premium.",
            choices=stats_utils.GATED_SUMMARIZE_BY,
        ),
    ) -> None:
        await self.make_summary_single_graph(
            ctx,
            summarize_by,
            "Playtime on the Realm over the past {days_humanized} by {summarize_by}",
        )

    @graph.subcommand(
        sub_cmd_name="player",
        sub_cmd_description=(
            "Produces a graph of a player's playtime over a specifed period as a graph."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(pl_utils.has_linked_realm)
    async def graph_player(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user to graph."),
        period: str = tansy.Option(
            "The period to graph by. Periods larger than 7 days requires a vote or"
            " Premium.",
            choices=stats_utils.GATED_PERIOD_TO_GRAPH,
        ),
    ) -> None:
        config = await ctx.fetch_config()

        xuid = await pl_utils.xuid_from_gamertag(self.bot, gamertag)
        await self.make_unsummary_single_graph(
            ctx,
            period,
            f"Playtime of {config.nicknames.get(xuid) or gamertag} over the last "
            + "{days_humanized}",
            individual=True,
            gamertag=gamertag,
            filter_kwargs={"xuid": xuid},
        )

    @graph.subcommand(
        sub_cmd_name="player-summary",
        sub_cmd_description=(
            "Summarizes a player over a specified period, by a specified interval."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(pl_utils.has_linked_realm)
    async def graph_player_summary(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user to graph."),
        summarize_by: str = tansy.Option(
            "What to summarize by. Periods larger than 7 days requires a vote or"
            " Premium.",
            choices=stats_utils.GATED_SUMMARIZE_BY,
        ),
    ) -> None:
        config = await ctx.fetch_config()

        xuid = await pl_utils.xuid_from_gamertag(self.bot, gamertag)
        await self.make_summary_single_graph(
            ctx,
            summarize_by,
            f"Playtime of {config.nicknames.get(xuid) or gamertag} over the past "
            + "{days_humanized} by {summarize_by}",
            gamertag=gamertag,
            filter_kwargs={"xuid": xuid},
        )

    @graph.subcommand(
        sub_cmd_name="multi-player",
        sub_cmd_description=(
            "Produces a graph of multiple players' playtime over a specifed period."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(pl_utils.has_linked_realm)
    @ipy.auto_defer(enabled=False)
    async def graph_multi_player(
        self,
        ctx: utils.RealmContext,
        period: str = tansy.Option(
            "The period to graph by. Periods larger than 7 days requires a vote or"
            " Premium.",
            choices=stats_utils.GATED_PERIOD_TO_GRAPH,
        ),
    ) -> None:
        config = await ctx.fetch_config()

        await stats_utils.period_parse(
            self.bot, ctx.author_id, config, period
        )  # verification check

        modal = ipy.Modal(
            ipy.InputText(
                label="What players do you want to graph?",
                style=ipy.TextStyles.PARAGRAPH,
                custom_id="gamertags",
                placeholder=(
                    "Gamertags only. For non-premium, max of 2 users - premium has 5."
                    " Use separate lines for players."
                ),
            ),
            title="Multi-Player Graph Input",
            custom_id=f"multi_player_graph|{period}",
        )
        await ctx.send_modal(modal)

    @graph.subcommand(
        sub_cmd_name="multi-player-summary",
        sub_cmd_description=(
            "Summarizes multiple players' playtime over a specified period, by a"
            " specified interval."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(pl_utils.has_linked_realm)
    @ipy.auto_defer(enabled=False)
    async def graph_multi_player_summary(
        self,
        ctx: utils.RealmContext,
        summarize_by: str = tansy.Option(
            "What to summarize by. Periods larger than 7 days requires a vote or"
            " Premium.",
            choices=stats_utils.GATED_SUMMARIZE_BY,
        ),
    ) -> None:
        config = await ctx.fetch_config()

        await stats_utils.summary_parse(
            self.bot, ctx.author_id, config, summarize_by
        )  # verification check

        modal = ipy.Modal(
            ipy.InputText(
                label="What players do you want to graph?",
                style=ipy.TextStyles.PARAGRAPH,
                custom_id="gamertags",
                placeholder=(
                    "Gamertags only. For non-premium, max of 2 users - premium has 5."
                    " Use separate lines for players."
                ),
            ),
            title="Multi-Player Summary Graph Input",
            custom_id=f"multi_player_summary_graph|{summarize_by}",
        )
        await ctx.send_modal(modal)

    @ipy.listen("modal_completion")
    @amazing_modal_error_handler
    async def multi_player_modals(self, event: ipy.events.ModalCompletion) -> None:
        ctx = typing.cast("utils.RealmModalContext", event.ctx)
        config = await ctx.fetch_config()

        if not ctx.custom_id.startswith("multi_player"):
            return

        gamertags = ctx.responses.get("gamertags")
        if not gamertags:
            raise ipy.errors.BadArgument("No gamertags were provided.")

        gamertags_list = list(
            dict.fromkeys(gamertags.splitlines())
        )  # basic order keeping dedupe

        limit = 5 if config.valid_premium else 2

        if len(gamertags_list) > limit:
            raise ipy.errors.BadArgument(
                "Too many gamertags were provided. The maximum for this server is"
                f" {limit}."
            )

        if len(gamertags_list) == 1:
            raise ipy.errors.BadArgument(
                "Cannot graph a single player using this command."
            )

        xuid_list = [
            await pl_utils.xuid_from_gamertag(self.bot, gamertag)
            for gamertag in gamertags_list
        ]

        if ctx.custom_id.startswith("multi_player_graph"):
            await self.multi_player_handle(ctx, xuid_list, gamertags_list)
        else:
            await self.multi_player_summary_handle(ctx, xuid_list, gamertags_list)

    @amazing_modal_error_handler
    async def handle_multi_players(
        self,
        ctx: utils.RealmModalContext,
        returned_data: (
            stats_utils.ProcessSummaryReturn | stats_utils.ProcessUnsummaryReturn
        ),
        now: datetime.datetime,
        xuid_list: list[str],
        gamertags: list[str],
    ) -> None:
        config = await ctx.fetch_config()

        time_data, earliest_datetime = await stats_utils.process_multi_graph_data(
            config,
            xuid_list,
            gamertag_list=gamertags,
            min_datetime=returned_data.min_datetime,
            now=now,
            func_to_use=returned_data.func_to_use,
        )
        graph = stats_utils.create_multi_graph(
            ctx,
            title=returned_data.formatted_title,
            bottom_label=returned_data.bottom_label,
            time_data=time_data,
            gamertags=[
                config.nicknames.get(x) or g
                for x, g in zip(xuid_list, gamertags, strict=True)
            ],
            localizations=returned_data.localizations,
            **(
                returned_data.template_kwargs
                if isinstance(returned_data, stats_utils.ProcessUnsummaryReturn)
                else {"max_value": None}
            ),
        )
        await stats_utils.send_graph(
            ctx,
            graph=graph,
            now=now,
            title=returned_data.formatted_title,
            min_datetime=returned_data.min_datetime,
            earliest_datetime=earliest_datetime,
        )

    @amazing_modal_error_handler
    async def multi_player_handle(
        self, ctx: utils.RealmModalContext, xuid_list: list[str], gamertags: list[str]
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)

        period_string = ctx.custom_id.split("|")[1]

        returned_data = await stats_utils.process_unsummary(
            ctx,
            now,
            period_string,
            "Playtime of various players over the last {days_humanized}",
            indivdual=True,
        )
        await self.handle_multi_players(ctx, returned_data, now, xuid_list, gamertags)

    @amazing_modal_error_handler
    async def multi_player_summary_handle(
        self, ctx: utils.RealmModalContext, xuid_list: list[str], gamertags: list[str]
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)

        summarize_by_string = ctx.custom_id.split("|")[1]

        returned_data = await stats_utils.process_summary(
            ctx,
            now,
            summarize_by_string,
            "Playtime of various players over the past {days_humanized} by"
            " {summarize_by}",
        )
        await self.handle_multi_players(ctx, returned_data, now, xuid_list, gamertags)

    @tansy.slash_command(
        name="leaderboard",
        description=(
            "Ranks users based on how many minutes they played on the Realm. Requires"
            " voting or Premium."
        ),
        dm_permission=False,
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 15)
    @ipy.check(pl_utils.has_linked_realm)
    async def leaderboard(
        self,
        ctx: utils.RealmContext | utils.RealmPrefixedContext,
        period: int = tansy.Option(
            "The period to gather data for.",
            choices=[
                ipy.SlashCommandChoice("24 hours", 1),
                ipy.SlashCommandChoice("1 week", 7),
                ipy.SlashCommandChoice("2 weeks", 14),
                ipy.SlashCommandChoice("30 days", 30),
            ],
        ),
        **kwargs: typing.Unpack[LeaderboardKwargs],
    ) -> None:
        config = await ctx.fetch_config()

        if (
            utils.SHOULD_VOTEGATE
            and not config.valid_premium
            and await self.bot.valkey.get(f"rpl-voted-{ctx.author.id}") != "1"
        ):
            await ctx.command.cooldown.reset(ctx)
            raise utils.CustomCheckFailure(
                "To use this command, you must vote for the bot through one of the"
                f" links listed in {self.bot.mention_command('vote')} or [purchase"
                " Playerlist Premium](https://playerlist.astrea.cc/wiki/premium.html)."
                " Voting lasts for 12 hours."
            )

        if period not in {1, 7, 14, 30}:
            raise utils.CustomCheckFailure("Invalid period given.")

        # this is genuinely some of the wackest code ive made
        # you wont like it

        now = ipy.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(days=period, minutes=1)
        min_datetime = now - time_delta

        datetimes = await stats_utils.gather_datetimes(config, min_datetime)

        earliest_datetime = min(d.joined_at for d in datetimes)
        warn_about_earliest = (
            min_datetime + datetime.timedelta(days=1) < earliest_datetime
        )

        leaderboard_counter_sort = stats_utils.calc_leaderboard(datetimes)
        if not leaderboard_counter_sort:
            raise utils.CustomCheckFailure(
                "There's no data for the linked Realm for this timespan."
            )

        if kwargs.get("autorunner"):
            leaderboard_counter_sort = leaderboard_counter_sort[:20]

        period_str = period_resolver(period)

        if warn_about_earliest and not kwargs.get("autorunner"):
            embed = ipy.Embed(
                title="Warning",
                description=(
                    "The bot does not have enough data to properly parse data for the"
                    " timespan you specified (most likely, you specified a timespan"
                    " that goes further back than when you first set up the bot with"
                    " your Realm). This data may be inaccurate."
                ),
                color=ipy.RoleColors.YELLOW,
            )
            await ctx.send(embed=embed)

        if len(leaderboard_counter_sort) > +20:
            pag = cclasses.DynamicLeaderboardPaginator(
                client=self.bot,
                pages_data=leaderboard_counter_sort,
                period_str=period_str,
                timestamp=now,
                nicknames=config.nicknames,
            )
            await pag.send(ctx)
            return

        gamertag_map = await pl_utils.get_xuid_to_gamertag_map(
            self.bot,
            [e[0] for e in leaderboard_counter_sort if e[0] not in config.nicknames],
        )

        leaderboard_builder: list[str] = []

        for index, (xuid, playtime) in enumerate(leaderboard_counter_sort):
            precisedelta = humanize.precisedelta(
                playtime, minimum_unit="minutes", format="%0.0f"
            )

            if precisedelta == "1 minutes":  # why humanize
                precisedelta = "1 minute"

            display = models.display_gamertag(
                xuid, gamertag_map[xuid], config.nicknames.get(xuid)
            )

            leaderboard_builder.append(f"**{index+1}\\.** {display}: {precisedelta}")

        await ctx.send(
            embed=utils.make_embed(
                "\n".join(leaderboard_builder),
                title=f"Leaderboard for the past {period_str}",
            )
        )

    @tansy.slash_command(
        name="get-player-log",
        description="Gets a log of every time a specific player joined and left.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    @ipy.check(pl_utils.has_linked_realm)
    async def get_player_log(
        self,
        ctx: utils.RealmContext,
        gamertag: str = tansy.Option("The gamertag of the user to get."),
        days_ago: int = tansy.Option(
            "How far the log should go (in days). Defaults to 1 day. Limit of 7 days.",
            min_value=1,
            max_value=7,
            default=1,
        ),
    ) -> None:
        """
        Gets a log of every time a specific player joined and left.

        Basically, the bot gathers up every time the player joined and left the Realm during \
        the timespan you specify and displays that to you.
        This information will only be gotten if the bot has been linked to the Realm for X \
        amount of days - otherwise, the best it is getting is partial data, likely to be \
        limited and slightly inaccurate.

        Has a cooldown of 5 seconds.
        """
        xuid = await pl_utils.xuid_from_gamertag(self.bot, gamertag)

        config = await ctx.fetch_config()

        now = ipy.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(days=days_ago, minutes=1)
        time_ago = now - time_delta

        sessions_str: list[str] = []
        total_playtime: float = 0.0

        async for session in models.PlayerSession.filter(
            Q(xuid=xuid)
            & Q(realm_id=str(config.realm_id))
            & (Q(online=True) | Q(last_seen__gte=time_ago)),
        ).order_by("-last_seen"):
            session_str: list[str] = []

            if session.joined_at:
                session_str.append(
                    f"**Joined:** <t:{int(session.joined_at.timestamp())}:f>"
                )
            if session.online:
                session_str.append("**Currently Online**")
            elif session.last_seen:
                session_str.append(
                    f"**Left:** <t:{int(session.last_seen.timestamp())}:f>"
                )

            if not session_str:
                continue

            if session.joined_at:
                last_seen = now if session.online else session.last_seen
                total_playtime += stats_utils.calc_timespan(
                    session.joined_at, last_seen
                )

            sessions_str.append("\n".join(session_str))

        if not sessions_str:
            raise utils.CustomCheckFailure(
                f"There is no data for `{gamertag}` for the last {days_ago} days on"
                " this Realm."
            )

        natural_playtime = humanize.naturaldelta(total_playtime)
        days_text = "day" if days_ago == 1 else "days"

        chunks = [sessions_str[x : x + 6] for x in range(0, len(sessions_str), 6)]

        # session number = (chunk index * 6) + (session-in-chunk index + 1) - () are added for clarity
        # why? well, say we're on the 3rd session chunk, and at the 5th entry for that chunk
        # the 3rd session chunk naturally means we have gone through (3 * 6) = 18 sessions beforehand,
        # so we know thats our minimum for this chunk
        # the session-in-chunk index is what we need to add to the "sessions beforehand" number
        # to get our original session str in the original list - we add one though because humans
        # don't index at 0
        embeds = [
            ipy.Embed(
                title=(
                    f"Log for {config.nicknames.get(xuid) or gamertag} for the past"
                    f" {days_ago} {days_text}"
                ),
                description=f"Total playtime over this period: {natural_playtime}",
                fields=[  # type: ignore
                    ipy.EmbedField(
                        f"Session {(chunk_index * 6) + (session_index + 1)}:",
                        session,
                        inline=True,
                    )
                    for session_index, session in enumerate(chunk)
                ],
                color=ctx.bot.color,
                footer=ipy.EmbedFooter("As of"),
                timestamp=now,
            )
            for chunk_index, chunk in enumerate(chunks)
        ]

        if len(embeds) == 1:
            await ctx.send(embeds=embeds)
        else:
            # the help paginator looks better than the default imo
            pag = help_tools.HelpPaginator.create_from_embeds(
                ctx.bot, *embeds, timeout=60
            )
            pag.show_callback_button = False
            await pag.send(ctx)

    misc_stats = tansy.TansySlashCommand(
        name="misc-stats",
        description="Calculates various extra/fun statistics.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )
    misc_stats.add_check(pl_utils.has_linked_realm)

    async def playtime_handle(
        self,
        ctx: utils.RealmContext,
        period: int,
        gamertag: typing.Optional[str],
    ) -> PlaytimeReturn:
        config = await ctx.fetch_config()

        xuid: typing.Optional[str] = None
        if gamertag:
            xuid = await pl_utils.xuid_from_gamertag(self.bot, gamertag)
        elif (
            utils.SHOULD_VOTEGATE
            and not config.valid_premium
            and await self.bot.valkey.get(f"rpl-voted-{ctx.author.id}") != "1"
        ):
            await ctx.command.cooldown.reset(ctx)
            raise utils.CustomCheckFailure(
                "To use this command, you must vote for the bot through one of the"
                f" links listed in {self.bot.mention_command('vote')} or [purchase"
                " Playerlist Premium](https://playerlist.astrea.cc/wiki/premium.html)."
                " Voting lasts for 12 hours."
            )

        if period not in {1, 7, 14, 30}:
            raise utils.CustomCheckFailure("Invalid period given.")

        now = ipy.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(days=period, minutes=1)
        time_ago = now - time_delta

        total_playtime: float = 0.0

        datetimes = await stats_utils.gather_datetimes(
            config, time_ago, gamertag=gamertag, xuid=xuid
        )

        earliest_datetime = min(d.joined_at for d in datetimes)
        warn_about_earliest = time_ago + datetime.timedelta(days=1) < earliest_datetime

        if not datetimes:
            raise utils.CustomCheckFailure(
                "There's no data for the linked Realm for this timespan."
            )

        for session in datetimes:
            total_playtime += stats_utils.calc_timespan(
                session.joined_at, session.last_seen
            )

        period_str = period_resolver(period)

        if warn_about_earliest and not gamertag:
            embed = ipy.Embed(
                title="Warning",
                description=(
                    "The bot does not have enough data to properly parse data for the"
                    " timespan you specified (most likely, you specified a timespan"
                    " that goes further back than when you first set up the bot with"
                    " your Realm). This data may be inaccurate."
                ),
                color=ipy.RoleColors.YELLOW,
            )
            await ctx.send(embed=embed)

        if gamertag:
            return PlaytimeReturn(total_playtime, period_str, len(datetimes))

        return PlaytimeReturn(
            total_playtime, period_str, len({d.xuid for d in datetimes})
        )

    @misc_stats.subcommand(
        sub_cmd_name="average-playtime",
        sub_cmd_description=(
            "Calculates the average playtime of all players or the specified player on"
            " the Realm."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    async def average_playtime(
        self,
        ctx: utils.RealmContext,
        period: int = tansy.Option(
            "The period to gather data for.",
            choices=[
                ipy.SlashCommandChoice("24 hours", 1),
                ipy.SlashCommandChoice("1 week", 7),
                ipy.SlashCommandChoice("2 weeks", 14),
                ipy.SlashCommandChoice("30 days", 30),
            ],
        ),
        gamertag: typing.Optional[str] = tansy.Option(
            "The player's gamertag. If not specified, calculates Realm wide, which"
            " requires voting or Premium.",
            default=None,
        ),
    ) -> None:
        playtime = await self.playtime_handle(ctx, period, gamertag)

        end_string = (
            "per session\n-# ℹ️ Essentially, they play, on average, that much time"  # noqa: RUF001
            " every time they join the Realm."
            if gamertag
            else "per player"
        )
        calc_playtime = round(playtime.total_playtime / playtime.length_to_use)

        await ctx.send(
            embed=utils.make_embed(
                f"Average playtime {f'for {gamertag}' if gamertag else ''} for the past"
                f" {playtime.period_str}:"
                f" {humanize.precisedelta(calc_playtime, minimum_unit='minutes', format='%0.0f')} {end_string}",
            )
        )

    @misc_stats.subcommand(
        sub_cmd_name="total-playtime",
        sub_cmd_description=(
            "Calculates the total playtime of all players or the specified player on"
            " the Realm."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    async def total_playtime(
        self,
        ctx: utils.RealmContext,
        period: int = tansy.Option(
            "The period to gather data for.",
            choices=[
                ipy.SlashCommandChoice("24 hours", 1),
                ipy.SlashCommandChoice("1 week", 7),
                ipy.SlashCommandChoice("2 weeks", 14),
                ipy.SlashCommandChoice("30 days", 30),
            ],
        ),
        gamertag: typing.Optional[str] = tansy.Option(
            "The player's gamertag. If not specified, calculates Realm wide, which"
            " requires voting or Premium.",
            default=None,
        ),
    ) -> None:
        playtime = await self.playtime_handle(ctx, period, gamertag)
        calc_playtime = round(playtime.total_playtime)

        await ctx.send(
            embed=utils.make_embed(
                f"Total playtime {f'for {gamertag}' if gamertag else ''} for the past"
                f" {playtime.period_str}:"
                f" {humanize.precisedelta(calc_playtime, minimum_unit='minutes', format='%0.0f')}",
            )
        )

    @misc_stats.subcommand(
        sub_cmd_name="longest-session",
        sub_cmd_description=(
            "Calculates the longest session on the Realm or by a player."
        ),
    )
    @ipy.cooldown(ipy.Buckets.GUILD, 1, 5)
    async def longest_session(
        self,
        ctx: utils.RealmContext,
        period: int = tansy.Option(
            "The period to gather data for.",
            choices=[
                ipy.SlashCommandChoice("24 hours", 1),
                ipy.SlashCommandChoice("1 week", 7),
                ipy.SlashCommandChoice("2 weeks", 14),
                ipy.SlashCommandChoice("30 days", 30),
            ],
        ),
        gamertag: typing.Optional[str] = tansy.Option(
            "The player's gamertag. If not specified, calculates Realm wide, which"
            " requires voting or Premium.",
            default=None,
        ),
    ) -> None:
        config = await ctx.fetch_config()

        xuid: typing.Optional[str] = None
        if gamertag:
            xuid = await pl_utils.xuid_from_gamertag(self.bot, gamertag)
        elif (
            utils.SHOULD_VOTEGATE
            and not config.valid_premium
            and await self.bot.valkey.get(f"rpl-voted-{ctx.author.id}") != "1"
        ):
            await ctx.command.cooldown.reset(ctx)
            raise utils.CustomCheckFailure(
                "To use this command, you must vote for the bot through one of the"
                f" links listed in {self.bot.mention_command('vote')} or [purchase"
                " Playerlist Premium](https://playerlist.astrea.cc/wiki/premium.html)."
                " Voting lasts for 12 hours."
            )

        if period not in {1, 7, 14, 30}:
            raise utils.CustomCheckFailure("Invalid period given.")

        now = ipy.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(days=period, minutes=1)
        time_ago = now - time_delta

        datetimes = await stats_utils.gather_datetimes(
            config, time_ago, gamertag=gamertag, xuid=xuid
        )
        if not datetimes:
            raise utils.CustomCheckFailure(
                "There's no data for the linked Realm for this timespan."
            )

        earliest_datetime = min(d.joined_at for d in datetimes)
        warn_about_earliest = time_ago + datetime.timedelta(days=1) < earliest_datetime

        biggest_range = max(
            datetimes, key=lambda d: stats_utils.calc_timespan(d.joined_at, d.last_seen)
        )

        if warn_about_earliest and not gamertag:
            embed = ipy.Embed(
                title="Warning",
                description=(
                    "The bot does not have enough data to properly parse data for the"
                    " timespan you specified (most likely, you specified a timespan"
                    " that goes further back than when you first set up the bot with"
                    " your Realm). This data may be inaccurate."
                ),
                color=ipy.RoleColors.YELLOW,
            )
            await ctx.send(embed=embed)

        delta = humanize.precisedelta(
            stats_utils.calc_timespan(biggest_range.joined_at, biggest_range.last_seen),
            minimum_unit="minutes",
            format="%0.0f",
        )

        if gamertag:
            await ctx.send(
                embed=utils.make_embed(
                    f"Longest session for {gamertag} for the past"
                    f" {period_resolver(period)}: {delta} long"
                    f" (from <t:{int(biggest_range.joined_at.timestamp())}:f> to"
                    f" <t:{int(biggest_range.last_seen.timestamp())}:f>)",
                )
            )
        else:
            try:
                longest_gamertag = (
                    f"`{await pl_utils.gamertag_from_xuid(self.bot, biggest_range.xuid)}`"
                )
            except ipy.errors.BadArgument:
                longest_gamertag = f"User with XUID `{biggest_range.xuid}`"

            await ctx.send(
                embed=utils.make_embed(
                    f"Longest session for the past {period_resolver(period)}:"
                    f" {delta} long, by {longest_gamertag} (from"
                    f" <t:{int(biggest_range.joined_at.timestamp())}:f> to"
                    f" <t:{int(biggest_range.last_seen.timestamp())}:f>)",
                )
            )


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(cclasses)
    importlib.reload(fuzzy)
    importlib.reload(stats_utils)
    importlib.reload(graph_template)
    importlib.reload(help_tools)
    Statistics(bot)
