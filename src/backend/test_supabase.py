"""
test_supabase.py — Test Supabase connection, seeding, and SupabaseDataSource

Usage:
    1. Set up .env with SUPABASE_URL and SUPABASE_ANON_KEY
    2. Run schema.sql in Supabase SQL Editor
    3. Run: python db/seed.py
    4. Then: python test_supabase.py

This verifies the full Supabase integration works end-to-end.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def main():
    print("=" * 60)
    print("🧪 TrialGuard AI — Supabase Integration Test")
    print("=" * 60)

    errors = []

    # Test 1: Check env vars
    print("\n[1/6] Checking environment variables...")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("   ❌ Missing SUPABASE_URL or SUPABASE_ANON_KEY in .env")
        print("   Set these in src/.env and try again.")
        return ["Missing env vars"]
    print(f"   ✅ SUPABASE_URL: {url[:40]}...")
    print(f"   ✅ Key present: {'ANON' if os.getenv('SUPABASE_ANON_KEY') else 'SERVICE_ROLE'}")

    # Test 2: Supabase client
    print("\n[2/6] Connecting to Supabase...")
    try:
        from db.supabase_client import get_supabase_client, is_supabase_configured
        assert is_supabase_configured(), "Supabase not configured"
        client = get_supabase_client()
        assert client is not None, "Client is None"
        print("   ✅ Supabase client connected")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"Supabase client: {e}")
        return errors

    # Test 3: Check tables have data
    print("\n[3/6] Checking table row counts...")
    tables = ["sites", "patients", "patient_visits", "deviations", "site_risk_profiles"]
    for table in tables:
        try:
            result = client.table(table).select("*", count="exact").limit(1).execute()
            count = result.count if hasattr(result, 'count') and result.count is not None else len(result.data)
            # Try alternative count method
            if count == 0 or count == 1:
                all_data = client.table(table).select("*").execute()
                count = len(all_data.data)
            print(f"   {'✅' if count > 0 else '⚠️ '} {table}: {count} rows")
            if count == 0:
                errors.append(f"Table {table} is empty — run `python db/seed.py` first")
        except Exception as e:
            print(f"   ❌ {table}: {e}")
            errors.append(f"Table {table}: {e}")

    if errors:
        print("\n   ⚠️  Some tables are empty. Run `python db/seed.py` to populate.")
        return errors

    # Test 4: SupabaseDataSource initialization
    print("\n[4/6] Initializing SupabaseDataSource...")
    try:
        from core.data_source import SupabaseDataSource
        sds = SupabaseDataSource()
        print(f"   ✅ SupabaseDataSource initialized")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"SupabaseDataSource init: {e}")
        return errors

    # Test 5: Query through SupabaseDataSource
    print("\n[5/6] Querying through SupabaseDataSource...")
    try:
        sites = sds.get_sites()
        print(f"   ✅ Sites: {len(sites)}")

        devs = sds.get_all_deviations()
        print(f"   ✅ Deviations: {len(devs)}")

        profiles = sds.get_risk_profiles()
        print(f"   ✅ Risk profiles: {len(profiles)}")
        if profiles:
            print(f"      Top risk: {profiles[0].site_id} (Score: {profiles[0].risk_score}/100)")

        site_devs = sds.get_deviations_for_site("SITE-001")
        print(f"   ✅ SITE-001 deviations: {len(site_devs)}")

        stats = sds.get_trial_statistics()
        print(f"   ✅ Trial stats: {stats['total_sites']} sites, {stats['total_patients']} patients")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"SupabaseDataSource queries: {e}")

    # Test 6: Compare Mock vs Supabase
    print("\n[6/6] Comparing MockDataSource vs SupabaseDataSource...")
    try:
        from core.data_source import MockDataSource
        mock = MockDataSource()
        
        mock_sites = len(mock.get_sites())
        supa_sites = len(sds.get_sites())
        
        mock_devs = len(mock.get_all_deviations())
        supa_devs = len(sds.get_all_deviations())
        
        print(f"   Mock sites: {mock_sites}, Supabase sites: {supa_sites} — {'✅ Match' if mock_sites == supa_sites else '⚠️ Mismatch'}")
        print(f"   Mock deviations: {mock_devs}, Supabase deviations: {supa_devs} — {'✅ Match' if mock_devs == supa_devs else '⚠️ Mismatch'}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"Comparison: {e}")

    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"❌ {len(errors)} test(s) FAILED:")
        for err in errors:
            print(f"   • {err}")
    else:
        print("✅ ALL 6 TESTS PASSED — Supabase integration working!")
    print("=" * 60)

    return errors


if __name__ == "__main__":
    errors = main()
    sys.exit(1 if errors else 0)
