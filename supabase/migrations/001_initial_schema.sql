-- ============================================================
-- Agentic Job Hunter — Initial Schema
-- ============================================================

-- search_tasks: Inserted by dashboard, consumed by local worker
CREATE TABLE IF NOT EXISTS search_tasks (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  job_title     text        NOT NULL,
  location      text        NOT NULL,
  min_salary    integer,
  keywords      text[],
  company       text,
  job_website   text,
  status        text        NOT NULL DEFAULT 'pending',
  -- Status values: pending | running | done | failed
  created_by    uuid        REFERENCES auth.users(id),
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- applications: Written by worker after each application attempt
CREATE TABLE IF NOT EXISTS applications (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  search_task_id  uuid        REFERENCES search_tasks(id),
  company         text        NOT NULL,
  job_title       text        NOT NULL,
  job_url         text        NOT NULL,
  status          text        NOT NULL,
  -- Status values: applied | failed | skipped
  requires_resume boolean     NOT NULL DEFAULT false,
  applied_at      timestamptz NOT NULL DEFAULT now(),
  error_message   text
);

-- email_logs: Written by email agent every 2 hours
CREATE TABLE IF NOT EXISTS email_logs (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  subject       text,
  sender        text,
  sentiment     text,
  -- Sentiment values: interest | rejection | spam
  summary       text,
  draft_link    text,
  received_at   timestamptz,
  synced_at     timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- Row Level Security
-- ============================================================

ALTER TABLE search_tasks  ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications   ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_logs     ENABLE ROW LEVEL SECURITY;

-- search_tasks: only the owning authenticated user can see/modify
CREATE POLICY "owner_search_tasks" ON search_tasks
  FOR ALL
  TO authenticated
  USING (auth.uid() = created_by)
  WITH CHECK (auth.uid() = created_by);

-- applications: any authenticated user (single-user system)
CREATE POLICY "auth_applications" ON applications
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- email_logs: any authenticated user
CREATE POLICY "auth_email_logs" ON email_logs
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- ============================================================
-- Public stats view (no company names, no personal data)
-- Used by the public dashboard page — no auth required
-- ============================================================

CREATE OR REPLACE VIEW public_stats AS
  SELECT
    DATE(applied_at) AS date,
    status,
    COUNT(*)::integer AS count
  FROM applications
  GROUP BY DATE(applied_at), status
  ORDER BY date DESC;

-- Grant anon access to the view only (not the table)
GRANT SELECT ON public_stats TO anon;
