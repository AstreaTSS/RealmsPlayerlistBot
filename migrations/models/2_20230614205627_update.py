from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "realmguildconfig" ADD "live_online_channel" VARCHAR(75);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "realmguildconfig" DROP COLUMN "live_online_channel";"""
