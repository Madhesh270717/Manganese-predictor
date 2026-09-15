-- Spotter AI — database bootstrap notes
--
-- With the Supabase (no-Docker) setup this file is NOT auto-executed: the
-- PostGIS extension is enabled manually once in the Supabase dashboard
-- (Database > Extensions > enable `postgis`), and Alembic migration 0001
-- also runs `CREATE EXTENSION IF NOT EXISTS postgis` as a safety net.
--
-- Migration 0008 verifies the extension actually serves PostGIS functions
-- before the schema migrations are considered complete.

CREATE EXTENSION IF NOT EXISTS postgis;
