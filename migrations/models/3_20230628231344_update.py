from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "realmpremiumcode" ADD "customer_id" VARCHAR(50);
        ALTER TABLE "realmpremiumcode" ADD "expires_at" TIMESTAMPTZ;
        ALTER TABLE "realmpremiumcode" ALTER COLUMN "max_uses" SET DEFAULT 2;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "realmpremiumcode" DROP COLUMN "customer_id";
        ALTER TABLE "realmpremiumcode" DROP COLUMN "expires_at";
        ALTER TABLE "realmpremiumcode" ALTER COLUMN "max_uses" SET DEFAULT 1;"""
