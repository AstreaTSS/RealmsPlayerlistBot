import asyncio
import collections
import contextlib
import datetime
import importlib

import naff
from dateutil.relativedelta import relativedelta

import common.classes as cclasses
import common.models as models
import common.playerlist_utils as pl_utils
import common.utils as utils


class AutoRunPlayerlist(utils.Extension):
    # the cog that controls the automatic version of the playerlist
    # this way, we can fix the main playerlist command itself without
    # resetting the autorun cycle

    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.playerlist_task = asyncio.create_task(self._start_playerlist())
        self.playerlist_realms_delete.start()

    def drop(self):
        self.playerlist_task.cancel()
        self.playerlist_realms_delete.stop()
        super().drop()

    async def _start_playerlist(self):
        await self.bot.fully_ready.wait()

        try:
            while True:
                # margin of error
                now = naff.Timestamp.utcnow() + datetime.timedelta(milliseconds=1)
                next_delta = relativedelta(hours=+1, minute=0, second=5, microsecond=0)
                next_time = now + next_delta

                await utils.sleep_until(next_time)

                upsell = next_time.hour % 4 == 0
                upsell_type = -1
                if upsell:
                    upsell_type = 1 if next_time.hour % 8 == 0 else 2

                await self.playerlist_loop(upsell, upsell_type)
        except Exception as e:
            if not isinstance(e, asyncio.CancelledError):
                await utils.error_handle(self.bot, e)

    @naff.Task.create(naff.IntervalTrigger(hours=6))
    async def playerlist_realms_delete(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        time_back = now - datetime.timedelta(hours=25)
        await models.RealmPlayer.filter(
            online=False,
            last_seen__lt=time_back,
        ).delete()

    async def playerlist_loop(self, upsell: bool = False, upsell_type: int = -1):
        """
        A simple way of running the playerlist command every hour in every server the bot is in.
        """

        list_cmd = next(
            c for c in self.bot.application_commands if str(c.name) == "playerlist"
        )
        to_run = []

        async for guild_config in models.GuildConfig.filter(
            guild_id__in=list(self.bot.user._guild_ids),
            club_id__not_isnull=True,
            realm_id__not_isnull=True,
            playerlist_chan__not_isnull=True,
            live_playerlist=False,
        ).prefetch_related("premium_code"):
            to_run.append(
                self.auto_run_playerlist(list_cmd, guild_config, upsell, upsell_type)
            )

        # this gather is done so that they can all run in parallel
        # should make things slightly faster for everyone
        output = await asyncio.gather(*to_run, return_exceptions=True)

        # all of this to send errors to the bot owner/me without
        # stopping this entirely
        for message in output:
            if isinstance(message, Exception):
                await utils.error_handle(self.bot, message)

    async def auto_run_playerlist(
        self,
        list_cmd: naff.InteractionCommand,
        guild_config: models.GuildConfig,
        upsell: bool = False,
        upsell_type: int = -1,
    ):
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

        try:
            chan = cclasses.valid_channel_check(chan)
        except naff.errors.BadArgument:
            with contextlib.suppress(naff.errors.HTTPException):
                await chan.send(
                    "I could not view message history for this channel when"
                    " automatically running the playerlist. This is needed in order to"
                    " run it automatically. Please make sure the bot has the ability to"
                    " read message history for this channel."
                )

            await pl_utils.eventually_invalidate(self.bot, guild_config)
            return

        # make a fake context to make things easier
        a_ctx: utils.RealmPrefixedContext = utils.RealmPrefixedContext(
            client=self.bot,  # type: ignore
            author=chan.guild.me,
            channel=chan,
            guild_id=chan._guild_id,
            guild_config=guild_config,
        )

        # take advantage of the fact that users cant really use kwargs for commands
        # the two listed here silence the 'this may take a long time' message
        # and also make it so it doesnt go back 12 hours, instead only going one
        await list_cmd.callback(
            a_ctx, "1", no_init_mes=True, upsell=upsell, upsell_type=upsell_type
        )


def setup(bot):
    importlib.reload(utils)
    importlib.reload(pl_utils)
    importlib.reload(cclasses)
    AutoRunPlayerlist(bot)
