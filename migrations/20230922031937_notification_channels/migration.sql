-- AlterTable
ALTER TABLE "realmguildconfig" ADD COLUMN     "notification_channels" JSONB NOT NULL DEFAULT '{}';
