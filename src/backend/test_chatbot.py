"""
test_chatbot.py — Unit & Integration tests for TrialGuard Assistant Chatbot

Verifies:
1. chatbot_service.py does NOT import mcp_server directly.
2. All tool calls execute through the genuine MCP client protocol.
3. Empty message handling
4. Trial summary query
5. Specific site risk query (SITE-042)
6. Top risk sites query
7. Site deviation query (SITE-001)
8. CAPA report generation query (SITE-042)
9. Missing site ID in CAPA query
10. Invalid site ID query (SITE-999)
11. Custom deviation classification query
12. Protocol / prohibited medications query
13. Unknown question fallback
"""

import sys
import os
import inspect
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

import chatbot_service
from chatbot_service import process_chat_message, extract_site_id
from mcp_client_service import get_mcp_status


async def run_async_tests():
    print("=" * 60)
    print("🤖 TrialGuard Assistant — MCP Client Protocol Chatbot Tests")
    print("=" * 60)
    
    passed = 0
    total = 0

    def assert_test(name, condition, details=""):
        nonlocal passed, total
        total += 1
        if condition:
            print(f"   ✅ [{total}] {name}")
            passed += 1
        else:
            print(f"   ❌ [{total}] {name} — FAILED: {details}")

    # Test 0: Verify Architectural Separation (chatbot_service does NOT import mcp_server)
    print("\n[Group 0] Architecture & Protocol Verification")
    chatbot_source = inspect.getsource(chatbot_service)
    assert_test("No direct 'import mcp_server' in chatbot_service", "import mcp_server" not in chatbot_source)
    assert_test("chatbot_service uses mcp_client_service", "from mcp_client_service import" in chatbot_source)
    
    mcp_status = await get_mcp_status()
    assert_test("Real MCP server connected via STDIO", mcp_status.get("connected") is True)
    assert_test("MCP discovered 5 tools", len(mcp_status.get("tools", [])) >= 5)

    # Test 1: Extract site IDs
    print("\n[Group 1] Site ID Extraction")
    assert_test("Extract SITE-042", extract_site_id("What is the risk of SITE-042?") == "SITE-042")
    assert_test("Extract site 001", extract_site_id("Show deviations for site 001") == "SITE-001")
    assert_test("Extract site-105", extract_site_id("generate capa for site-105") == "SITE-105")
    assert_test("No site in general query", extract_site_id("Give me a trial summary") is None)

    # Test 2: Empty message
    print("\n[Group 2] Empty message handling")
    res_empty = await process_chat_message("")
    assert_test("Empty string response", "TrialGuard Assistant" in res_empty["reply"])
    assert_test("Empty string suggestions", len(res_empty["suggestions"]) > 0)

    # Test 3: Trial Summary (via MCP get_trial_summary tool)
    print("\n[Group 3] Trial Summary Queries (via MCP)")
    res_summary = await process_chat_message("Give me a trial summary")
    assert_test("Summary contains PHOENIX-301", "PHOENIX-301" in res_summary["reply"])
    assert_test("Summary tool used", res_summary["tool_used"] == "get_trial_summary")

    # Test 4: Site Risk (via MCP score_site_risk tool)
    print("\n[Group 4] Site Risk Queries (via MCP)")
    res_risk_42 = await process_chat_message("What is the risk of SITE-042?")
    assert_test("Risk score for SITE-042", "SITE-042" in res_risk_42["reply"] and "Risk Score" in res_risk_42["reply"])
    assert_test("Risk tool used", res_risk_42["tool_used"] == "score_site_risk")
    assert_test("Site ID returned", res_risk_42["site_id"] == "SITE-042")

    res_top_risk = await process_chat_message("Which sites are highest risk?")
    assert_test("Top risk sites list", "Highest-Risk Sites" in res_top_risk["reply"])
    assert_test("Top risk tool used", res_top_risk["tool_used"] == "score_site_risk")

    # Test 5: Deviations (via MCP detect_deviations tool)
    print("\n[Group 5] Deviation Queries (via MCP)")
    res_dev = await process_chat_message("What problems does SITE-001 have?")
    assert_test("Deviations for SITE-001", "Deviations for SITE-001" in res_dev["reply"] or "No deviations found" in res_dev["reply"])
    assert_test("Deviation tool used", res_dev["tool_used"] == "detect_deviations")
    assert_test("Site ID returned", res_dev["site_id"] == "SITE-001")

    # Test 6: CAPA Report (via MCP generate_capa_report tool)
    print("\n[Group 6] CAPA Report Queries (via MCP)")
    res_capa = await process_chat_message("Generate CAPA for SITE-042")
    assert_test("CAPA report generated", "CORRECTIVE AND PREVENTIVE ACTION" in res_capa["reply"] or "CAPA" in res_capa["reply"])
    assert_test("CAPA tool used", res_capa["tool_used"] == "generate_capa_report")

    res_capa_nosite = await process_chat_message("Show me a CAPA report")
    assert_test("CAPA prompts for site ID", "specify the site ID" in res_capa_nosite["reply"])

    # Test 7: Invalid Site ID (SITE-999)
    print("\n[Group 7] Invalid Site Handling")
    res_invalid = await process_chat_message("What is the risk of SITE-999?")
    assert_test("Invalid site flagged", "SITE-999" in res_invalid["reply"] and "not found" in res_invalid["reply"])

    # Test 8: Custom Deviation Classification (via MCP classify_deviation tool)
    print("\n[Group 8] Deviation Classification (via MCP)")
    res_class = await process_chat_message("Classify a missed visit by patient")
    assert_test("ICH E6 Classification returned", "MAJOR" in res_class["reply"] and "ICH E6" in res_class["reply"])
    assert_test("Classification tool used", res_class["tool_used"] == "classify_deviation")

    # Test 9: Protocol & Prohibited Drugs (via MCP resource trial://protocol)
    print("\n[Group 9] Protocol Info (via MCP Resource)")
    res_proto = await process_chat_message("What are the prohibited medications in PHOENIX-301?")
    assert_test("Protocol rules returned", "Prohibited Medications" in res_proto["reply"])

    # Test 10: Help & Unknown questions
    print("\n[Group 10] Help and Fallback")
    res_help = await process_chat_message("What can you do?")
    assert_test("Help response", "TrialGuard Assistant Capabilities" in res_help["reply"])

    res_unknown = await process_chat_message("What is the weather in Paris?")
    assert_test("Fallback response", "not sure how to answer" in res_unknown["reply"] and len(res_unknown["suggestions"]) > 0)

    pct = (passed / total) * 100 if total > 0 else 0.0
    print("\n" + "=" * 60)
    print(f"📊 Results: {passed}/{total} tests passed ({pct:.1f}%)")
    print("=" * 60)
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_async_tests())
    sys.exit(0 if success else 1)
