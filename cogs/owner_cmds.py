import asyncio
import importlib
import os

import nextcord
from nextcord.ext import application_checks
from nextcord.ext import commands
from nextcord.types.interactions import PartialGuildApplicationCommandPermissions

import common.utils as utils
from common.models import GuildConfig

DEV_GUILD_ID = int(os.environ["DEV_GUILD_ID"])


class OwnerCMDs(commands.Cog, name="Owner", command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot: utils.RealmBotBase = bot
        self.bot.loop.create_task(self.add_permissions())

    async def add_permissions(self):
        while not hasattr(self, "owner"):
            await asyncio.sleep(0.1)

        # thanks, nextcord!
        await asyncio.sleep(5)

        cmd_dicts = []

        app_commands = self.bot._connection.application_commands
        for cmd in app_commands:
            if cmd.type == nextcord.ApplicationCommandType.chat_input and cmd.name in (
                "view-guild",
                "add-guild",
                "edit-guild",
                "remove-guild",
                "edit-guild-via-id",
            ):
                cmd_id = cmd.command_ids[DEV_GUILD_ID]
                cmd_dict: PartialGuildApplicationCommandPermissions = {
                    "id": cmd_id,
                    "permissions": [
                        {
                            "id": self.bot.owner_id,
                            "type": 2,
                            "permission": True,
                        }
                    ],
                }
                cmd_dicts.append(cmd_dict)

        if cmd_dicts:
            await self.bot.http.bulk_edit_guild_application_command_permissions(
                self.bot.application_id, DEV_GUILD_ID, cmd_dicts  # type: ignore
            )

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    def _limit_to_25(self, mapping: dict):
        return dict(tuple(mapping.items())[:25])

    async def _autocomplete_guilds(self, inter: nextcord.Interaction, argument: str):
        guild_mapping = {guild.name: str(guild.id) for guild in self.bot.guilds}

        if not argument:
            await inter.response.send_autocomplete(self._limit_to_25(guild_mapping))
            return

        near_guilds = {
            guild_name: guild_id
            for guild_name, guild_id in guild_mapping.items()
            if argument.lower() in guild_name.lower()
        }
        await inter.response.send_autocomplete(self._limit_to_25(near_guilds))

    def error_embed_generate(self, error_msg):
        return nextcord.Embed(colour=nextcord.Colour.red(), description=error_msg)

    @nextcord.slash_command(
        name="view-guild",
        description="Displays a guild's config. Can only be used by the bot's owner.",
        guild_ids=[DEV_GUILD_ID],
        default_permission=False,
    )
    @application_checks.is_owner()
    async def view_guild(
        self,
        inter: nextcord.Interaction,
        guild_id: str = nextcord.SlashOption(  # type: ignore
            name="guild", description="The guild to view."
        ),
    ):
        await inter.response.defer()

        guild = self.bot.get_guild(int(guild_id))
        guild_config = await GuildConfig.get(guild_id=int(guild_id))

        prefixes = tuple(f"`{p}`" for p in guild_config.prefixes)

        embed = nextcord.Embed(
            color=self.bot.color, title=f"Server Config for {guild}:"
        )
        playerlist_channel = (
            f"<#{guild_config.playerlist_chan}> ({guild_config.playerlist_chan})"
            if guild_config.playerlist_chan
            else "None"
        )
        embed.description = (
            f"Club ID: {guild_config.club_id}\n"
            + f"Playerlist Channel: {playerlist_channel}\nOnline Command Enabled?"
            f" {guild_config.online_cmd}\nPrefixes: {', '.join(prefixes)}"
        )

        await inter.send(embed=embed)

    @view_guild.on_autocomplete("guild_id")
    async def view_get_guild(self, inter, argument):
        await self._autocomplete_guilds(inter, argument)

    @nextcord.slash_command(
        name="add-guild",
        description=(
            "Adds a guild to the bot's configs. Can only be used by the bot's owner."
        ),
        guild_ids=[DEV_GUILD_ID],
        default_permission=False,
    )
    @application_checks.is_owner()
    async def add_guild(
        self,
        inter: nextcord.Interaction,
        guild_id: str = nextcord.SlashOption(  # type: ignore
            description="The guild ID for the guild to add."
        ),
        club_id: str = nextcord.SlashOption(  # type: ignore
            description="The club ID for the Realm.", required=False
        ),
        playerlist_chan: str = nextcord.SlashOption(  # type: ignore
            description="The playerlist channel ID for this guild.", required=False
        ),
        online_cmd: bool = nextcord.SlashOption(  # type: ignore
            description="Should the online command be able to be used?", required=False
        ),
    ):
        await inter.response.defer()

        kwargs = {"guild_id": int(guild_id), "prefixes": {"!?"}}

        if club_id:
            kwargs["club_id"] = club_id
        if playerlist_chan:
            kwargs["playerlist_chan"] = int(playerlist_chan)
        if online_cmd:
            kwargs["online_cmd"] = online_cmd

        await GuildConfig.create(**kwargs)
        await inter.send("Done!")

    @nextcord.slash_command(
        name="edit-guild",
        description=(
            "Edits a guild in the bot's configs. Can only be used by the bot's owner."
        ),
        guild_ids=[DEV_GUILD_ID],
        default_permission=False,
    )
    @application_checks.is_owner()
    async def edit_guild(
        self,
        inter: nextcord.Interaction,
        guild_id: str = nextcord.SlashOption(  # type: ignore
            name="guild", description="The guild ID for the guild to edit."
        ),
        club_id: str = nextcord.SlashOption(  # type: ignore
            description="The club ID for the Realm.", required=False
        ),
        playerlist_chan: str = nextcord.SlashOption(  # type: ignore
            description="The playerlist channel ID for this guild.", required=False
        ),
        online_cmd: bool = nextcord.SlashOption(  # type: ignore
            description="Should the online command be able to be used?", required=False
        ),
    ):
        await inter.response.defer()

        guild_config = await GuildConfig.get(guild_id=int(guild_id))

        if club_id:
            guild_config.club_id = club_id if club_id != "None" else None
        if playerlist_chan:
            guild_config.playerlist_chan = (
                int(playerlist_chan) if playerlist_chan != "None" else None
            )
        if online_cmd:
            guild_config.online_cmd = online_cmd

        await guild_config.save()
        await inter.send("Done!")

    @nextcord.slash_command(
        name="edit-guild-via-id",
        description=(
            "Edits a guild in the bot's configs. Can only be used by the bot's owner."
        ),
        guild_ids=[DEV_GUILD_ID],
        default_permission=False,
    )
    @application_checks.is_owner()
    async def edit_guild_via_id(
        self,
        inter: nextcord.Interaction,
        guild_id: str = nextcord.SlashOption(  # type: ignore
            description="The guild ID for the guild to edit."
        ),
        club_id: str = nextcord.SlashOption(  # type: ignore
            description="The club ID for the Realm.", required=False
        ),
        playerlist_chan: str = nextcord.SlashOption(  # type: ignore
            description="The playerlist channel ID for this guild.", required=False
        ),
        online_cmd: bool = nextcord.SlashOption(  # type: ignore
            description="Should the online command be able to be used?", required=False
        ),
    ):
        await inter.response.defer()

        guild_config = await GuildConfig.get(guild_id=int(guild_id))

        if club_id:
            guild_config.club_id = club_id if club_id != "None" else None
        if playerlist_chan:
            guild_config.playerlist_chan = (
                int(playerlist_chan) if playerlist_chan != "None" else None
            )
        if online_cmd:
            guild_config.online_cmd = online_cmd

        await guild_config.save()
        await inter.send("Done!")

    @nextcord.slash_command(
        name="remove-guild",
        description=(
            "Removes a guild from the bot's configs. Can only be used by the bot's"
            " owner."
        ),
        guild_ids=[DEV_GUILD_ID],
        default_permission=False,
    )
    @application_checks.is_owner()
    async def remove_guild(
        self,
        inter: nextcord.Interaction,
        guild_id: str = nextcord.SlashOption(  # type: ignore
            name="guild", description="The guild ID for the guild to remove."
        ),
    ):
        await inter.response.defer()
        await GuildConfig.filter(guild_id=int(guild_id)).delete()
        await inter.send("Deleted!")

    @edit_guild.on_autocomplete("guild_id")
    async def edit_get_guild(self, inter, argument):
        await self._autocomplete_guilds(inter, argument)

    @commands.Cog.listener()
    async def on_application_command_error(
        self, inter: nextcord.Interaction, error: Exception
    ):
        if isinstance(error, nextcord.ApplicationError):
            await inter.send(embed=self.error_embed_generate(str(error)))
        else:
            await utils.error_handle(self.bot, error, inter)


def setup(bot):
    importlib.reload(utils)
    bot.add_cog(OwnerCMDs(bot))
