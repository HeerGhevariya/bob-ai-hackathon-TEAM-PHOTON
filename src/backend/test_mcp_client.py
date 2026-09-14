"""
test_mcp_client.py — Test real MCP Client connection, tool execution & resource reading over STDIO
"""

import sys
import os
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

from mcp_client_service import get_mcp_status, call_mcp_tool, get_mcp_resource


async def run_mcp_tests():
    print("=" * 60)
    print("🔌 TrialGuard AI — MCP Client Protocol Verification Test")
    print("=" * 60)

    # 1. Test MCP Status & Tool Discovery
    print("\n[1/5] Testing MCP Handshake & Tool Discovery...")
    status = await get_mcp_status()
    print("   Status connected:", status.get("connected"))
    print("   Transport:", status.get("transport"))
    assert status.get("connected") is True, f"Failed to connect: {status.get('error')}"
    tools = status.get("tools", [])
    print(f"   ✅ Discovered {len(tools)} tools: {', '.join(tools)}")
    assert "get_trial_summary" in tools
    assert "score_site_risk" in tools
    assert "detect_deviations" in tools
    assert "generate_capa_report" in tools
    assert "classify_deviation" in tools

    # 2. Test Tool Call: get_trial_summary
    print("\n[2/5] Calling MCP Tool via JSON-RPC: get_trial_summary()...")
    summary = await call_mcp_tool("get_trial_summary")
    print("   Output preview:\n  ", summary[:120].replace("\n", "\n   "))
    assert "PHOENIX-301" in summary
    print("   ✅ get_trial_summary returned valid protocol data over MCP")

    # 3. Test Tool Call: score_site_risk
    print("\n[3/5] Calling MCP Tool via JSON-RPC: score_site_risk(site_id='SITE-042')...")
    risk = await call_mcp_tool("score_site_risk", {"site_id": "SITE-042"})
    print("   Output preview:\n  ", risk[:120].replace("\n", "\n   "))
    assert "SITE-042" in risk
    print("   ✅ score_site_risk returned valid risk data over MCP")

    # 4. Test Tool Call: detect_deviations
    print("\n[4/5] Calling MCP Tool via JSON-RPC: detect_deviations(site_id='SITE-001')...")
    devs = await call_mcp_tool("detect_deviations", {"site_id": "SITE-001"})
    print("   Output preview:\n  ", devs[:120].replace("\n", "\n   "))
    assert "SITE-001" in devs or "No deviations" in devs
    print("   ✅ detect_deviations returned valid deviation data over MCP")

    # 5. Test MCP Resource: trial://protocol
    print("\n[5/5] Reading MCP Resource: trial://protocol...")
    proto = await get_mcp_resource("trial://protocol")
    print("   Output preview:\n  ", proto[:120].replace("\n", "\n   "))
    assert "PHOENIX-301" in proto
    print("   ✅ trial://protocol read successfully over MCP")

    print("\n" + "=" * 60)
    print("🎉 ALL MCP CLIENT PROTOCOL TESTS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_mcp_tests())
    sys.exit(0 if success else 1)
