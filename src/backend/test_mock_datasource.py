"""
test_mock_datasource.py — Smoke test for MockDataSource (no Supabase needed)

Usage:
    cd src/backend
    python test_mock_datasource.py
"""

import sys
import os

# Ensure imports work
sys.path.insert(0, os.path.dirname(__file__))

def main():
    print("=" * 60)
    print("🧪 TrialGuard AI — MockDataSource Smoke Test")
    print("=" * 60)
    
    errors = []

    # Test 1: DataSource initialization
    print("\n[1/8] Initializing DataSource (should be MockDataSource)...")
    try:
        from core.data_source import get_data_source
        ds = get_data_source()
        ds_type = type(ds).__name__
        assert ds_type == "MockDataSource", f"Expected MockDataSource, got {ds_type}"
        print(f"   ✅ DataSource: {ds_type}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"DataSource init: {e}")
        return errors

    # Test 2: Protocol
    print("\n[2/8] Loading protocol...")
    try:
        protocol = ds.get_protocol()
        assert protocol.protocol_id == "PHOENIX-301"
        print(f"   ✅ Protocol: {protocol.protocol_id} — {protocol.protocol_title}")
        print(f"      Visits: {len(protocol.visits)}, Dose rules: {len(protocol.dose_rules)}, Banned meds: {len(protocol.banned_medications)}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"Protocol: {e}")

    # Test 3: Sites
    print("\n[3/8] Loading sites...")
    try:
        sites = ds.get_sites()
        assert len(sites) > 200, f"Expected 200+ sites, got {len(sites)}"
        print(f"   ✅ Sites loaded: {len(sites)}")
        
        # Test single site lookup
        site = ds.get_site("SITE-001")
        assert site is not None
        print(f"   ✅ Single site lookup: {site.site_id} — {site.site_name} ({site.city}, {site.country})")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"Sites: {e}")

    # Test 4: Deviations
    print("\n[4/8] Loading deviations...")
    try:
        all_devs = ds.get_all_deviations()
        assert len(all_devs) > 0, "No deviations found"
        
        from collections import Counter
        sev = Counter(d.severity for d in all_devs)
        print(f"   ✅ Total deviations: {len(all_devs)}")
        print(f"      🔴 Major: {sev.get('major', 0)}, 🟡 Minor: {sev.get('minor', 0)}, 🔵 Admin: {sev.get('administrative', 0)}")

        # Test site-specific deviations
        site_devs = ds.get_deviations_for_site("SITE-001")
        print(f"   ✅ SITE-001 deviations: {len(site_devs)}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"Deviations: {e}")

    # Test 5: Risk Profiles
    print("\n[5/8] Loading risk profiles...")
    try:
        profiles = ds.get_risk_profiles()
        assert len(profiles) > 0, "No risk profiles"
        
        tier_counts = Counter(rp.risk_tier.value for rp in profiles)
        print(f"   ✅ Risk profiles: {len(profiles)}")
        print(f"      🔴 Critical: {tier_counts.get('critical', 0)}, 🟠 High: {tier_counts.get('high', 0)}, 🟡 Medium: {tier_counts.get('medium', 0)}, 🟢 Low: {tier_counts.get('low', 0)}")
        print(f"   ✅ Top risk: {profiles[0].site_id} — {profiles[0].site_name} (Score: {profiles[0].risk_score}/100)")

        # Test single profile
        rp = ds.get_risk_profile(profiles[0].site_id)
        assert rp is not None
        print(f"   ✅ Single profile lookup works")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"Risk profiles: {e}")

    # Test 6: CAPA Report
    print("\n[6/8] Generating CAPA report...")
    try:
        test_site_id = profiles[0].site_id if profiles else "SITE-001"
        test_site = ds.get_site(test_site_id)
        test_devs = ds.get_deviations_for_site(test_site_id)
        test_rp = ds.get_risk_profile(test_site_id)
        
        report = ds.generate_capa_report(
            site_id=test_site_id,
            site_name=test_site.site_name,
            deviations=test_devs,
            risk_profile=test_rp,
        )
        assert report.full_report_markdown, "Empty CAPA report"
        print(f"   ✅ CAPA report generated: {report.report_id}")
        print(f"      Total findings: {report.total_findings}")
        print(f"      Corrective actions: {len(report.corrective_actions)}")
        print(f"      Report length: {len(report.full_report_markdown)} chars")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"CAPA report: {e}")

    # Test 7: FHIR Export
    print("\n[7/8] Testing FHIR R4 export...")
    try:
        from core.fhir_adapter import site_to_fhir_bundle, patient_to_fhir, deviation_to_fhir
        
        test_site = ds.get_site("SITE-001")
        test_devs = ds.get_deviations_for_site("SITE-001")
        
        bundle = site_to_fhir_bundle(test_site, deviations=test_devs)
        assert bundle["resourceType"] == "Bundle"
        assert bundle["total"] > 0
        print(f"   ✅ FHIR Bundle: {bundle['total']} entries for SITE-001")
        
        # Check resource types in the bundle
        resource_types = Counter(e["resource"]["resourceType"] for e in bundle["entry"])
        for rt, count in resource_types.most_common():
            print(f"      {rt}: {count}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"FHIR export: {e}")

    # Test 8: Trial Statistics
    print("\n[8/8] Getting trial statistics...")
    try:
        stats = ds.get_trial_statistics()
        print(f"   ✅ Trial stats:")
        print(f"      Sites: {stats['total_sites']}")
        print(f"      Patients: {stats['total_patients']}")
        print(f"      Visits: {stats['total_visits']}")
        print(f"      Countries: {stats['countries']}")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        errors.append(f"Statistics: {e}")

    # Summary
    print("\n" + "=" * 60)
    if errors:
        print(f"❌ {len(errors)} test(s) FAILED:")
        for err in errors:
            print(f"   • {err}")
    else:
        print("✅ ALL 8 TESTS PASSED — MockDataSource is working correctly!")
    print("=" * 60)
    
    return errors


if __name__ == "__main__":
    errors = main()
    sys.exit(1 if errors else 0)
