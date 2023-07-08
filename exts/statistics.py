import datetime
import importlib
import typing

import humanize
import interactions as ipy
import rapidfuzz
import tansy
from interactions.models.internal.application_commands import auto_defer
from tortoise.expressions import Q

import common.fuzzy as fuzzy
import common.graph_template as graph_template
import common.help_tools as help_tools
import common.models as models
import common.playerlist_utils as pl_utils
import common.stats_utils as stats_utils
import common.utils as utils

AsyncCallableT = typing.TypeVar("AsyncCallableT", bound=ipy.const.AsyncCallable)


def amazing_modal_error_handler(func: AsyncCallableT) -> AsyncCallableT:
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
        period: str = tansy.Option("The period to graph by.", autocomplete=True),
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
        summarize_by: str = tansy.Option("What to summarize by.", autocomplete=True),
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
        period: str = tansy.Option("The period to graph by.", autocomplete=True),
    ) -> None:
        xuid = await stats_utils.xuid_from_gamertag(self.bot, gamertag)
        await self.make_unsummary_single_graph(
            ctx,
            period,
            f"Playtime of {gamertag} over the last " + "{days_humanized}",
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
        summarize_by: str = tansy.Option("What to summarize by.", autocomplete=True),
    ) -> None:
        xuid = await stats_utils.xuid_from_gamertag(self.bot, gamertag)
        await self.make_summary_single_graph(
            ctx,
            summarize_by,
            f"Playtime of {gamertag} over the past "
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
    @auto_defer(enabled=False)
    async def graph_multi_player(
        self,
        ctx: utils.RealmContext,
        period: str = tansy.Option("The period to graph by.", autocomplete=True),
    ) -> None:
        config = await ctx.fetch_config()

        stats_utils.period_parse(config, period)  # verification check

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
    @auto_defer(enabled=False)
    async def graph_multi_player_summary(
        self,
        ctx: utils.RealmContext,
        summarize_by: str = tansy.Option("What to summarize by.", autocomplete=True),
    ) -> None:
        config = await ctx.fetch_config()

        stats_utils.summary_parse(config, summarize_by)  # verification check

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
        ctx = typing.cast(utils.RealmModalContext, event.ctx)
        config = await ctx.fetch_config()

        if not ctx.custom_id.startswith("multi_player"):
            return

        gamertags = ctx.responses.get("gamertags")
        if not gamertags:
            raise ipy.errors.BadArgument("No gamertags were provided.")

        gamertags_list = gamertags.splitlines()

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
            await stats_utils.xuid_from_gamertag(self.bot, gamertag)
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
        returned_data: stats_utils.ProcessSummaryReturn
        | stats_utils.ProcessUnsummaryReturn,
        now: datetime.datetime,
        xuid_list: list[str],
        gamertags: list[str],
    ) -> None:
        time_data, earliest_datetime = await stats_utils.process_multi_graph_data(
            await ctx.fetch_config(),
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
            gamertags=gamertags,
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
            (
                "Playtime of various players over the past {days_humanized} by"
                " {summarize_by}"
            ),
        )
        await self.handle_multi_players(ctx, returned_data, now, xuid_list, gamertags)

    @staticmethod
    def _filter_for_fuzzy(period_summary: str | dict[str, typing.Any]) -> str:
        if isinstance(period_summary, str):
            return period_summary.lower()
        return period_summary["name"].lower()

    @graph_realm.autocomplete("period")
    @graph_player.autocomplete("period")
    @graph_multi_player.autocomplete("period")
    async def period_autocomplete(
        self,
        ctx: utils.RealmAutocompleteContext,
    ) -> None:
        period = ctx.kwargs.get("period")

        config = await ctx.fetch_config()
        periods = (
            stats_utils.PREMIUM_PERIOD_TO_GRAPH
            if config.valid_premium
            else stats_utils.PERIOD_TO_GRAPH
        )
        periods_dict = [{"name": str(p.name), "value": p.value} for p in periods]

        if not period:
            await ctx.send(periods_dict)
            return

        filtered_periods = fuzzy.extract_from_list(
            period.lower(),
            periods_dict,
            (self._filter_for_fuzzy,),
            score_cutoff=80,
            scorers=(rapidfuzz.fuzz.WRatio,),
        )
        await ctx.send(p[0] for p in filtered_periods)

    @graph_realm_summary.autocomplete("summarize_by")
    @graph_player_summary.autocomplete("summarize_by")
    @graph_multi_player_summary.autocomplete("summarize_by")
    async def summary_autocomplete(
        self,
        ctx: utils.RealmAutocompleteContext,
    ) -> None:
        summarize_by = ctx.kwargs.get("summarize_by")

        config = await ctx.fetch_config()
        summarize_bys = (
            stats_utils.PREMIUM_SUMMARIZE_BY
            if config.valid_premium
            else stats_utils.SUMMARIZE_BY
        )
        summary_dict = [{"name": str(s.name), "value": s.value} for s in summarize_bys]

        if not summarize_by:
            await ctx.send(summary_dict)
            return

        filtered_summaries = fuzzy.extract_from_list(
            summarize_by.lower(),
            summary_dict,
            (self._filter_for_fuzzy,),
            score_cutoff=80,
            scorers=(rapidfuzz.fuzz.WRatio,),
        )
        await ctx.send(s[0] for s in filtered_summaries)

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
        xuid = await stats_utils.xuid_from_gamertag(self.bot, gamertag)

        config = await ctx.fetch_config()

        now = ipy.Timestamp.utcnow().replace(second=30)
        time_delta = datetime.timedelta(days=days_ago, minutes=1)
        time_ago = now - time_delta

        sessions_str: list[str] = []
        total_playtime: float = 0.0

        async for session in models.PlayerSession.filter(
            Q(xuid=xuid)
            & Q(realm_id=config.realm_id)
            & Q(Q(online=True) | Q(last_seen__gte=time_ago))
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
                total_playtime += last_seen.timestamp() - session.joined_at.timestamp()

            sessions_str.append("\n".join(session_str))

        if not sessions_str:
            raise utils.CustomCheckFailure(
                f"There is no data for `{gamertag}` for the last {days_ago} days on"
                " this Realm."
            )

        natural_playtime = humanize.naturaldelta(total_playtime)

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
                title=f"Log for {gamertag} for the past {days_ago} days(s)",
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


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(stats_utils)
    importlib.reload(graph_template)
    importlib.reload(help_tools)
    Statistics(bot)
