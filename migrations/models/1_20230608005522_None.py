from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "realmplayersession" (
    "custom_id" UUID NOT NULL  PRIMARY KEY,
    "realm_id" VARCHAR(50) NOT NULL,
    "xuid" VARCHAR(50) NOT NULL,
    "online" BOOL NOT NULL  DEFAULT False,
    "last_seen" TIMESTAMPTZ NOT NULL,
    "joined_at" TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS "idx_realmplayer_realm_i_b7a049" ON "realmplayersession" ("realm_id", "xuid", "last_seen", "joined_at");
CREATE TABLE IF NOT EXISTS "realmpremiumcode" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "code" VARCHAR(100) NOT NULL,
    "user_id" BIGINT,
    "uses" INT NOT NULL  DEFAULT 0,
    "max_uses" INT NOT NULL  DEFAULT 1
);
CREATE TABLE IF NOT EXISTS "realmguildconfig" (
    "guild_id" BIGSERIAL NOT NULL PRIMARY KEY,
    "club_id" VARCHAR(50),
    "playerlist_chan" BIGINT,
    "realm_id" VARCHAR(50),
    "live_playerlist" BOOL NOT NULL  DEFAULT False,
    "realm_offline_role" BIGINT,
    "warning_notifications" BOOL NOT NULL  DEFAULT True,
    "fetch_devices" BOOL NOT NULL  DEFAULT False,
    "premium_code_id" INT REFERENCES "realmpremiumcode" ("id") ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
