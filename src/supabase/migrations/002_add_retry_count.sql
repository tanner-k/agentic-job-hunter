-- Add retry_count to applications table.
-- Allows the --retry-failed worker mode to cap retries and prevent infinite loops.
ALTER TABLE applications ADD COLUMN IF NOT EXISTS retry_count integer NOT NULL DEFAULT 0;
