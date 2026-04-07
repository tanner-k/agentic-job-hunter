# Supabase Migrations

Apply these migrations via the Supabase dashboard SQL editor or CLI:

```bash
supabase db push
```

Or manually: copy the SQL from each file and run in Supabase Studio → SQL Editor.

## Files

- `001_initial_schema.sql` — Creates search_tasks, applications, email_logs tables with RLS policies and public_stats view.
