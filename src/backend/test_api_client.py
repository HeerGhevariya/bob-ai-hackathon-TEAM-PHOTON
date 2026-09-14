"""
Test FastAPI endpoints directly in-process via Starlette / FastAPI TestClient or direct app calls.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from api import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_all():
    print("Testing /api/trial/summary...")
    r = client.get("/api/trial/summary")
    assert r.status_code == 200, f"Error: {r.status_code}"
    print("  ✅ /api/trial/summary OK")

    print("Testing /api/mcp/status...")
    r = client.get("/api/mcp/status")
    assert r.status_code == 200
    assert r.json().get("connected") is True
    assert "get_trial_summary" in r.json().get("tools", [])
    print(f"  ✅ /api/mcp/status OK (Connected: {r.json().get('connected')}, Tools: {len(r.json().get('tools', []))})")

    print("Testing /api/chat/suggestions...")
    r = client.get("/api/chat/suggestions")
    assert r.status_code == 200
    assert len(r.json()["suggestions"]) > 0
    print("  ✅ /api/chat/suggestions OK")

    print("Testing /api/chat (Trial Summary)...")
    r = client.post("/api/chat", json={"message": "Give me a trial summary"})
    assert r.status_code == 200
    assert "PHOENIX-301" in r.json()["reply"]
    print("  ✅ /api/chat Trial Summary OK")

    print("Testing /api/chat (Site Risk SITE-042)...")
    r = client.post("/api/chat", json={"message": "What is the risk of SITE-042?"})
    assert r.status_code == 200
    assert "SITE-042" in r.json()["reply"]
    print("  ✅ /api/chat Site Risk OK")

    print("Testing /api/chat (CAPA SITE-042)...")
    r = client.post("/api/chat", json={"message": "Generate CAPA for SITE-042"})
    assert r.status_code == 200
    assert r.json()["tool_used"] == "generate_capa_report"
    print("  ✅ /api/chat CAPA OK")

    print("\n🎉 ALL API IN-PROCESS TESTS PASSED!")

if __name__ == "__main__":
    test_all()
