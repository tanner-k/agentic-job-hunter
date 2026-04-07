from functools import lru_cache

from supabase import Client, create_client
from worker.config import settings


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Return the Supabase client singleton.

    Uses the service role key so the worker can read/write all rows
    regardless of RLS policies. The worker is a trusted local process.
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
