"""
Copyright 2020-2024 AstreaTSS.
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

from prisma.models import GuildConfig, PlayerSession

GuildConfig.create_partial(
    "PrismaAutorunGuildConfig",
    include=(
        "guild_id",
        "fetch_devices",
        "realm_id",
        "playerlist_chan",
        "nicknames",
        "premium_code",
    ),
    required=("playerlist_chan", "realm_id"),
)

PlayerSession.create_partial("AutorunPlayerSession", include=("xuid",))
