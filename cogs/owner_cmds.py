import asyncio

import nextcord
from nextcord.ext import commands
from nextcord.types.interactions import PartialGuildApplicationCommandPermissions

import common.utils as utils
from common.models import GuildConfig


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
            ):
                cmd_id = cmd.command_ids[775912554928144384]
                cmd_dict: PartialGuildApplicationCommandPermissions = {
                    "id": cmd_id,
                    "permissions": [
                        {"id": self.bot.owner_id, "type": 2, "permission": True,}
                    ],
                }
                cmd_dicts.append(cmd_dict)

        if cmd_dicts:
            await self.bot.http.bulk_edit_guild_application_command_permissions(
                self.bot.application_id, 775912554928144384, cmd_dicts
            )

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @nextcord.slash_command(
        name="view-guild",
        description="Displays a guild's config.",
        guild_ids=[775912554928144384],
        default_permission=False,
    )
    async def view_guild(
        self,
        inter: nextcord.Interaction,
        guild_id: str = nextcord.SlashOption(  # type: ignore
            description="The guild ID for the guild to view."
        ),
    ):
        await inter.response.defer()

        guild = self.bot.get_guild(int(guild_id))
        guild_config = await GuildConfig.get(guild_id=guild_id)

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

    @nextcord.slash_command(
        name="add-guild",
        description="Adds a guild to the bot's configs.",
        guild_ids=[775912554928144384],
        default_permission=False,
    )
    async def add_guild(
        self,
        inter: nextcord.Interaction,
        guild_id: str = nextcord.SlashOption(  # type: ignore
            description="The guild ID for the guild to add."
        ),
    ):
        await inter.response.defer()
        await GuildConfig.create(
            guild_id=int(guild_id), prefixes={"!?"},
        )
        await inter.send("Done!")

    @nextcord.slash_command(
        name="edit-guild",
        description="Edits a guild in the bot's configs.",
        guild_ids=[775912554928144384],
        default_permission=False,
    )
    async def edit_guild(
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

        guild_config = await GuildConfig.get(guild_id=guild_id)

        if club_id:
            guild_config.club_id = int(club_id) if club_id != "None" else None
        if playerlist_chan:
            guild_config.playerlist_chan = (
                int(playerlist_chan) if playerlist_chan != "None" else None
            )
        if online_cmd:
            guild_config.online_cmd = online_cmd

        await guild_config.save()
        await inter.send("Done!")


def setup(bot):
    bot.add_cog(OwnerCMDs(bot))
