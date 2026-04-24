from __future__ import annotations

from src.arkana_auth.supabase_connector import SupabaseClientError, SupabaseConnector


class SupabaseClient(SupabaseConnector):
    pass


__all__ = ["SupabaseClient", "SupabaseClientError", "SupabaseConnector"]
