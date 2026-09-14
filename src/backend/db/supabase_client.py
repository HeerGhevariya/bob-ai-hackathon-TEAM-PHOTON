"""
supabase_client.py — Supabase Client Initialization

Provides a singleton Supabase client for database operations.
Reads connection details from environment variables.
"""

import os
from typing import Optional

from dotenv import load_dotenv

# Load .env from the src/ directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


_client = None


def get_supabase_client():
    """
    Get or create the Supabase client singleton.

    Returns None if Supabase is not configured (missing SUPABASE_URL).
    """
    global _client

    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        return _client
    except ImportError:
        print("⚠️  supabase-py not installed. Install with: pip install supabase")
        return None
    except Exception as e:
        print(f"⚠️  Failed to connect to Supabase: {e}")
        return None


def is_supabase_configured() -> bool:
    """Check if Supabase environment variables are set."""
    return bool(os.getenv("SUPABASE_URL") and (
        os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    ))
