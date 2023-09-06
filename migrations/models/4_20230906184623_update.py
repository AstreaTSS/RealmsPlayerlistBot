from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "realmguildconfig" ADD "player_watchlist_role" BIGINT;
        ALTER TABLE "realmguildconfig" ADD "player_watchlist" TEXT[];"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "realmguildconfig" DROP COLUMN "player_watchlist_role";
        ALTER TABLE "realmguildconfig" DROP COLUMN "player_watchlist";"""
