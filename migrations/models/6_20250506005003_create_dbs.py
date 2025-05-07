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

from tortoise import BaseDBAsyncClient


async def upgrade(_: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "realmpremiumcode" (
        "id" SERIAL NOT NULL PRIMARY KEY,
        "code" VARCHAR(100) NOT NULL,
        "user_id" INT NOT NULL,
        "uses" INT NOT NULL DEFAULT 0,
        "max_uses" INT NOT NULL DEFAULT 2,
        "customer_id" VARCHAR(50),
        "expires_at" TIMESTAMPTZ
    );
        CREATE TABLE IF NOT EXISTS "realmguildconfig" (
    "guild_id" SERIAL NOT NULL PRIMARY KEY,
    "club_id" VARCHAR(50),
    "playerlist_chan" INT NOT NULL,
    "realm_id" VARCHAR(50),
    "live_playerlist" BOOL NOT NULL DEFAULT False,
    "realm_offline_role" INT NOT NULL,
    "warning_notifications" BOOL NOT NULL DEFAULT True,
    "fetch_devices" BOOL NOT NULL DEFAULT False,
    "live_online_channel" VARCHAR(75),
    "player_watchlist_role" INT NOT NULL,
    "player_watchlist" TEXT[],
    "notification_channels" JSONB NOT NULL,
    "reoccurring_leaderboard" INT NOT NULL,
    "nicknames" JSONB NOT NULL,
    "premium_code_id" INT REFERENCES "realmpremiumcode" ("id") ON DELETE SET NULL
);
        CREATE TABLE IF NOT EXISTS "realmplayersession" (
    "custom_id" UUID NOT NULL PRIMARY KEY,
    "realm_id" VARCHAR(50) NOT NULL,
    "xuid" VARCHAR(50) NOT NULL,
    "online" BOOL NOT NULL DEFAULT False,
    "last_seen" TIMESTAMPTZ NOT NULL,
    "joined_at" TIMESTAMPTZ
);
"""


async def downgrade(_: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "realmguildconfig";
        DROP TABLE IF EXISTS "realmplayersession";
        DROP TABLE IF EXISTS "realmpremiumcode";"""
