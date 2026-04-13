-- 004_add_failure_logs_table.sql
-- Adds the failure_logs table for structured pipeline failure reporting.
-- Only failed records are inserted, so failed_reason is NOT NULL.

create table if not exists failure_logs (
    id            uuid        primary key default gen_random_uuid(),
    step          text        not null,
    failed_reason text        not null,
    job_url       text        not null,
    created_at    timestamptz not null default now()
);

-- Index for querying failures by step (most common dashboard filter)
create index if not exists idx_failure_logs_step on failure_logs (step);

-- Index for recent-failures queries
create index if not exists idx_failure_logs_created_at on failure_logs (created_at desc);
