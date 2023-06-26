import asyncio
import datetime
import importlib

import interactions as ipy
from dateutil.relativedelta import relativedelta

import common.classes as cclasses
import common.models as models
import common.playerlist_utils as pl_utils
import common.utils as utils

UPSELLS = [
    (
        "Want minute-to-minute updates on your Realm? Do you want device information"
        " for players? Check out Playerlist Premium: /premium info"
    ),
    (
        "If you like the bot, you can vote for it via /vote! Voting helps the bot grow"
        " and get more features!"
    ),
]
LENGTH_UPSELLS = len(UPSELLS)


def upsell_determiner(dt: datetime.datetime) -> str | None:
    if dt.hour % 4 == 0:
        total_seconds = int(dt.timestamp())
        x_hour_boundary = total_seconds % (14400 * LENGTH_UPSELLS)
        return UPSELLS[x_hour_boundary // 14400]

    return None


class AutoRunPlayerlist(utils.Extension):
    # the cog that controls the automatic version of the playerlist
    # this way, we can fix the main playerlist command itself without
    # resetting the autorun cycle

    def __init__(self, bot: utils.RealmBotBase) -> None:
        self.bot: utils.RealmBotBase = bot
        self.playerlist_task = self.bot.create_task(self._start_playerlist())
        self.player_session_delete.start()

    def drop(self) -> None:
        self.playerlist_task.cancel()
        self.player_session_delete.stop()
        super().drop()

    async def _start_playerlist(self) -> None:
        await self.bot.fully_ready.wait()

        try:
            while True:
                # margin of error
                now = ipy.Timestamp.utcnow() + datetime.timedelta(milliseconds=1)
                next_delta = relativedelta(hours=+1, minute=0, second=5, microsecond=0)
                next_time = now + next_delta

                await utils.sleep_until(next_time)

                await self.playerlist_loop(upsell=upsell_determiner(next_time))
        except Exception as e:
            if not isinstance(e, asyncio.CancelledError):
                await utils.error_handle(e)

    @ipy.Task.create(ipy.TimeTrigger())
    async def player_session_delete(self) -> None:
        now = datetime.datetime.now(tz=datetime.UTC)
        time_back = now - datetime.timedelta(days=31)
        await models.PlayerSession.filter(
            online=False,
            last_seen__lt=time_back,
        ).delete()

    async def playerlist_loop(
        self,
        upsell: str | None,
    ) -> None:
        """
        A simple way of running the playerlist command every hour in every server the bot is in.
        """

        list_cmd = next(
            c for c in self.bot.application_commands if str(c.name) == "playerlist"
        )
        to_run = []

        async for guild_config in models.GuildConfig.filter(
            guild_id__in=list(self.bot.user._guild_ids),
            realm_id__not_isnull=True,
            playerlist_chan__not_isnull=True,
            live_playerlist=False,
        ).prefetch_related("premium_code"):
            to_run.append(self.auto_run_playerlist(list_cmd, guild_config, upsell))

        # this gather is done so that they can all run in parallel
        # should make things slightly faster for everyone
        output = await asyncio.gather(*to_run, return_exceptions=True)

        # all of this to send errors to the bot owner/me without
        # stopping this entirely
        for message in output:
            if isinstance(message, Exception):
                await utils.error_handle(message)

    async def auto_run_playerlist(
        self,
        list_cmd: ipy.InteractionCommand,
        guild_config: models.GuildConfig,
        upsell: str | None,
    ) -> None:
        guild = self.bot.get_guild(guild_config.guild_id)
        if not guild:
            # could just be it's offline or something
            return

        try:
            chan = await pl_utils.fetch_playerlist_channel(
                self.bot, guild, guild_config
            )
        except ValueError:
            return

        # make a fake context to make things easier
        a_ctx = utils.RealmPrefixedContext(client=self.bot)
        a_ctx.author_id = self.bot.user.id
        a_ctx.channel_id = chan.id
        a_ctx.guild_id = chan._guild_id
        a_ctx.guild_config = guild_config

        a_ctx.prefix = ""
        a_ctx.content_parameters = ""
        a_ctx.command = None  # type: ignore
        a_ctx.args = []
        a_ctx.kwargs = {}

        # take advantage of the fact that users cant really use kwargs for commands
        # the ones listed here silence the 'this may take a long time' message
        # and also make it so it doesnt go back 12 hours, instead only going one
        # and yes, add the upsell info

        try:
            await list_cmd.callback(
                a_ctx,
                1,
                autorunner=True,
                upsell=upsell,
            )
        except ipy.errors.HTTPException:
            # likely a can't send in channel, eventually invalidate and move on
            await pl_utils.eventually_invalidate(self.bot, guild_config)


def setup(bot: utils.RealmBotBase) -> None:
    importlib.reload(utils)
    importlib.reload(pl_utils)
    importlib.reload(cclasses)
    AutoRunPlayerlist(bot)
