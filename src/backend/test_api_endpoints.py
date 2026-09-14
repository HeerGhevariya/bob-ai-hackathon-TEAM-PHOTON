"""
test_api_endpoints.py — Test all FastAPI endpoints including FHIR export

Usage:
    1. Start the backend: python main.py
    2. In another terminal: python test_api_endpoints.py
"""

import sys
import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8080"

def test_endpoint(name, path, check_fn=None):
    """Test a single API endpoint."""
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if check_fn:
                check_fn(data)
            print(f"   ✅ {name} — OK")
            return True
    except urllib.error.HTTPError as e:
        print(f"   ❌ {name} — HTTP {e.code}: {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"   ❌ {name} — Connection failed: {e.reason}")
        return False
    except Exception as e:
        print(f"   ❌ {name} — {e}")
        return False


def main():
    print("=" * 60)
    print("🧪 TrialGuard AI — API Endpoint Tests")
    print(f"   Base URL: {BASE_URL}")
    print("=" * 60)

    results = []

    # Test 1: Trial Summary
    print("\n[1/7] GET /api/trial/summary")
    results.append(test_endpoint(
        "Trial Summary",
        "/api/trial/summary",
        lambda d: (
            assert_key(d, "trial"),
            assert_key(d, "overview"),
            assert_key(d, "deviations"),
            assert_key(d, "risk_distribution"),
            assert_key(d, "alerts"),
        )
    ))

    # Test 2: Sites List
    print("\n[2/7] GET /api/sites")
    results.append(test_endpoint(
        "Sites List",
        "/api/sites?limit=10&offset=0",
        lambda d: (
            assert_key(d, "total"),
            assert_key(d, "sites"),
            assert_true(len(d["sites"]) > 0, "No sites returned"),
        )
    ))

    # Test 3: Site Detail
    print("\n[3/7] GET /api/sites/SITE-001")
    results.append(test_endpoint(
        "Site Detail",
        "/api/sites/SITE-001",
        lambda d: (
            assert_key(d, "site"),
            assert_key(d, "risk_profile"),
            assert_key(d, "deviations"),
            assert_key(d, "patients"),
        )
    ))

    # Test 4: Deviations
    print("\n[4/7] GET /api/deviations")
    results.append(test_endpoint(
        "Deviations List",
        "/api/deviations?limit=10",
        lambda d: (
            assert_key(d, "total"),
            assert_key(d, "deviations"),
        )
    ))

    # Test 5: CAPA Report
    print("\n[5/7] GET /api/capa/SITE-001")
    results.append(test_endpoint(
        "CAPA Report",
        "/api/capa/SITE-001",
        lambda d: (
            assert_key(d, "report_id"),
            assert_key(d, "full_report_markdown"),
            assert_true(len(d["full_report_markdown"]) > 100, "CAPA report too short"),
        )
    ))

    # Test 6: Trends
    print("\n[6/7] GET /api/trends")
    results.append(test_endpoint(
        "Trends",
        "/api/trends",
        lambda d: (
            assert_key(d, "monthly_deviations"),
            assert_key(d, "deviation_type_distribution"),
        )
    ))

    # Test 7: FHIR Export
    print("\n[7/7] GET /api/export/fhir/SITE-001")
    results.append(test_endpoint(
        "FHIR R4 Bundle Export",
        "/api/export/fhir/SITE-001",
        lambda d: (
            assert_true(d.get("resourceType") == "Bundle", f"Expected Bundle, got {d.get('resourceType')}"),
            assert_true(d.get("total", 0) > 0, "Empty FHIR bundle"),
            print(f"      FHIR Bundle: {d['total']} entries"),
        )
    ))

    # Bonus: Data Source Info
    print("\n[Bonus] GET /api/data-source")
    results.append(test_endpoint(
        "Data Source Info",
        "/api/data-source",
        lambda d: print(f"      Data source: {d.get('type')} — {d.get('description')}")
    ))

    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    print("\n" + "=" * 60)
    if passed == total:
        print(f"✅ ALL {total} TESTS PASSED!")
    else:
        print(f"⚠️  {passed}/{total} tests passed, {total - passed} failed")
    print("=" * 60)

    return 0 if passed == total else 1


def assert_key(data, key):
    if key not in data:
        raise AssertionError(f"Missing key: '{key}'")

def assert_true(condition, msg):
    if not condition:
        raise AssertionError(msg)


if __name__ == "__main__":
    sys.exit(main())
