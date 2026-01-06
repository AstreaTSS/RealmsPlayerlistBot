"""
Copyright 2020-2026 AstreaTSS.
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
        ALTER TABLE "realmguildconfig" ALTER COLUMN "guild_id" TYPE BIGINT USING "guild_id"::BIGINT;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "reoccurring_leaderboard" DROP NOT NULL;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "playerlist_chan" TYPE BIGINT USING "playerlist_chan"::BIGINT;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "realm_offline_role" DROP NOT NULL;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "realm_offline_role" TYPE BIGINT USING "realm_offline_role"::BIGINT;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "player_watchlist_role" DROP NOT NULL;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "player_watchlist_role" TYPE BIGINT USING "player_watchlist_role"::BIGINT;
        ALTER TABLE "realmpremiumcode" ALTER COLUMN "user_id" DROP NOT NULL;
        ALTER TABLE "realmpremiumcode" ALTER COLUMN "user_id" TYPE BIGINT USING "user_id"::BIGINT;"""


async def downgrade(_: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "realmguildconfig" ALTER COLUMN "guild_id" TYPE INT USING "guild_id"::INT;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "reoccurring_leaderboard" SET NOT NULL;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "playerlist_chan" TYPE INT USING "playerlist_chan"::INT;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "realm_offline_role" TYPE INT USING "realm_offline_role"::INT;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "realm_offline_role" SET NOT NULL;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "player_watchlist_role" TYPE INT USING "player_watchlist_role"::INT;
        ALTER TABLE "realmguildconfig" ALTER COLUMN "player_watchlist_role" SET NOT NULL;
        ALTER TABLE "realmpremiumcode" ALTER COLUMN "user_id" TYPE INT USING "user_id"::INT;
        ALTER TABLE "realmpremiumcode" ALTER COLUMN "user_id" SET NOT NULL;"""
