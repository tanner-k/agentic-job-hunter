-- Enable Supabase Realtime for the applications table.
-- Required for the dashboard's useApplicationsRealtime hook to receive live updates.
-- Apply manually via Supabase SQL Editor after running 001_initial.sql.
ALTER PUBLICATION supabase_realtime ADD TABLE applications;
