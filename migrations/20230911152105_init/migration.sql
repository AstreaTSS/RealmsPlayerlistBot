-- CreateTable
CREATE TABLE "realmguildconfig" (
    "guild_id" BIGSERIAL NOT NULL,
    "club_id" VARCHAR(50),
    "playerlist_chan" BIGINT,
    "realm_id" VARCHAR(50),
    "live_playerlist" BOOLEAN NOT NULL DEFAULT false,
    "realm_offline_role" BIGINT,
    "warning_notifications" BOOLEAN NOT NULL DEFAULT true,
    "premium_code_id" INTEGER,
    "fetch_devices" BOOLEAN NOT NULL DEFAULT false,
    "live_online_channel" VARCHAR(75),
    "player_watchlist_role" BIGINT,
    "player_watchlist" TEXT[] DEFAULT ARRAY[]::TEXT[],

    CONSTRAINT "realmguildconfig_pkey" PRIMARY KEY ("guild_id")
);

-- CreateTable
CREATE TABLE "realmplayersession" (
    "custom_id" UUID NOT NULL,
    "realm_id" VARCHAR(50) NOT NULL,
    "xuid" VARCHAR(50) NOT NULL,
    "online" BOOLEAN NOT NULL DEFAULT false,
    "last_seen" TIMESTAMPTZ(6) NOT NULL,
    "joined_at" TIMESTAMPTZ(6),

    CONSTRAINT "realmplayersession_pkey" PRIMARY KEY ("custom_id")
);

-- CreateTable
CREATE TABLE "realmpremiumcode" (
    "id" SERIAL NOT NULL,
    "code" VARCHAR(100) NOT NULL,
    "user_id" BIGINT,
    "uses" INTEGER NOT NULL DEFAULT 0,
    "max_uses" INTEGER NOT NULL DEFAULT 2,
    "customer_id" VARCHAR(50),
    "expires_at" TIMESTAMPTZ(6),

    CONSTRAINT "realmpremiumcode_pkey" PRIMARY KEY ("id")
);

-- AddForeignKey
ALTER TABLE "realmguildconfig" ADD CONSTRAINT "realmguildconfig_premium_code_id_fkey" FOREIGN KEY ("premium_code_id") REFERENCES "realmpremiumcode"("id") ON DELETE SET NULL ON UPDATE NO ACTION;
