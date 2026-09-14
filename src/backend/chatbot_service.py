"""
chatbot_service.py — Deterministic Dialogue Manager for TrialGuard Assistant

Orchestrates conversational queries against the clinical trial analysis engine
exclusively through the genuine MCP Client protocol (mcp_client_service.py).
Operates 100% deterministically without external LLM dependencies, ensuring
zero latency, reliable responses, and full ICH GCP audit compliance.
"""

import sys
import os
import re
import asyncio
from typing import Optional, Tuple, Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

from mcp_client_service import call_mcp_tool, get_mcp_resource
from core.data_source import get_data_source


def extract_site_id(text: str) -> Optional[str]:
    """
    Safely extract a site ID from text (e.g., 'SITE-042', 'site 42', 'site-001').
    Normalizes to standard 'SITE-XXX' format.
    """
    if not text:
        return None
    
    # Match SITE-042, SITE_042, SITE 042, SITE042, or site 42
    match = re.search(r'\b(?:site)[-_ ]?(\d{1,4})\b', text, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        return f"SITE-{num:03d}"
    return None


def get_default_suggestions() -> List[str]:
    """Return default starter prompt suggestions for the chat UI."""
    return [
        "📊 Give me a trial summary",
        "🔴 Which sites are highest risk?",
        "🔍 What is the risk of SITE-042?",
        "⚠️ Show deviations for SITE-001",
        "📋 Generate CAPA for SITE-042",
        "❓ What can you do?",
    ]


async def process_chat_message(message: str) -> Dict[str, Any]:
    """
    Process an incoming user message asynchronously and return a structured response
    by invoking tools over the genuine MCP Client protocol.
    
    Returns:
        dict: {
            "reply": str,
            "tool_used": Optional[str],
            "suggestions": List[str],
            "site_id": Optional[str]
        }
    """
    raw_text = (message or "").strip()
    
    # 0. Handle Empty Message
    if not raw_text:
        return {
            "reply": "👋 Hello! I am **TrialGuard Assistant**, your AI clinical compliance partner. How can I help you monitor the PHOENIX-301 trial today?",
            "tool_used": None,
            "suggestions": get_default_suggestions(),
            "site_id": None,
        }
    
    text_lower = raw_text.lower()
    site_id = extract_site_id(raw_text)
    ds = get_data_source()
    
    # Check if a site ID was extracted and validate existence in trial registry
    site_exists = ds.get_site(site_id) is not None if site_id else False
    
    # ─── 1. CAPA Report Queries ──────────────────────────────────────────
    if "capa" in text_lower or "corrective action" in text_lower:
        if site_id:
            if not site_exists:
                return {
                    "reply": f"⚠️ **Site '{site_id}' was not found** in the PHOENIX-301 trial registry.\n\nPlease check the site identifier (valid format is `SITE-001` through `SITE-210`).",
                    "tool_used": None,
                    "suggestions": ["Show highest risk sites", "Generate CAPA for SITE-042", "Generate CAPA for SITE-001"],
                    "site_id": site_id,
                }
            
            report_md = await call_mcp_tool("generate_capa_report", {"site_id": site_id})
            return {
                "reply": report_md,
                "tool_used": "generate_capa_report",
                "suggestions": [
                    f"Show deviations for {site_id}",
                    f"What is the risk of {site_id}?",
                    "Give me a trial summary",
                ],
                "site_id": site_id,
            }
        else:
            # CAPA requested without site ID
            return {
                "reply": "📋 To generate a regulatory-standard **CAPA (Corrective and Preventive Action) Report**, please specify the site ID.\n\n**Example queries:**\n- `Generate CAPA for SITE-042`\n- `Show CAPA report for SITE-001`\n- `CAPA SITE-105`",
                "tool_used": None,
                "suggestions": [
                    "Generate CAPA for SITE-042",
                    "Generate CAPA for SITE-001",
                    "Show highest risk sites",
                ],
                "site_id": None,
            }
    
    # ─── 2. Deviations Queries ───────────────────────────────────────────
    if any(k in text_lower for k in ["deviation", "deviations", "violations", "problems", "issues", "findings"]):
        if site_id:
            if not site_exists:
                return {
                    "reply": f"⚠️ **Site '{site_id}' was not found** in the PHOENIX-301 trial registry.\n\nPlease check the site identifier (valid format is `SITE-001` through `SITE-210`).",
                    "tool_used": None,
                    "suggestions": ["Show highest risk sites", "Show deviations for SITE-001", "Give me a trial summary"],
                    "site_id": site_id,
                }
            
            dev_result = await call_mcp_tool("detect_deviations", {"site_id": site_id})
            return {
                "reply": dev_result,
                "tool_used": "detect_deviations",
                "suggestions": [
                    f"What is the risk of {site_id}?",
                    f"Generate CAPA for {site_id}",
                    "Trial-wide deviation summary",
                ],
                "site_id": site_id,
            }
        else:
            # Trial-wide deviations summary
            dev_summary = await call_mcp_tool("detect_deviations", {"site_id": ""})
            return {
                "reply": dev_summary,
                "tool_used": "detect_deviations",
                "suggestions": [
                    "Show deviations for SITE-042",
                    "Show deviations for SITE-001",
                    "Which sites are highest risk?",
                ],
                "site_id": None,
            }
    
    # ─── 3. Site Risk Queries ────────────────────────────────────────────
    if any(k in text_lower for k in ["risk", "score", "tier", "critical", "highest risk", "leaderboard", "worst"]):
        if site_id:
            if not site_exists:
                return {
                    "reply": f"⚠️ **Site '{site_id}' was not found** in the PHOENIX-301 trial database.\n\nValid sites range from `SITE-001` to `SITE-210`.",
                    "tool_used": None,
                    "suggestions": ["Show highest risk sites", "What is the risk of SITE-042?", "Give me a trial summary"],
                    "site_id": site_id,
                }
            
            risk_result = await call_mcp_tool("score_site_risk", {"site_id": site_id})
            return {
                "reply": risk_result,
                "tool_used": "score_site_risk",
                "suggestions": [
                    f"Show deviations for {site_id}",
                    f"Generate CAPA for {site_id}",
                    "Show highest risk sites",
                ],
                "site_id": site_id,
            }
        else:
            # Top risk sites leaderboard
            top_risk = await call_mcp_tool("score_site_risk", {"top_n": 5})
            return {
                "reply": top_risk,
                "tool_used": "score_site_risk",
                "suggestions": [
                    "What is the risk of SITE-042?",
                    "Generate CAPA for SITE-042",
                    "Give me a trial summary",
                ],
                "site_id": None,
            }
    
    # ─── 4. Trial Summary & Overview Queries ─────────────────────────────
    if any(k in text_lower for k in ["summary", "overview", "status", "health", "how is the trial", "stats", "statistics"]):
        summary = await call_mcp_tool("get_trial_summary", {})
        return {
            "reply": summary,
            "tool_used": "get_trial_summary",
            "suggestions": [
                "Which sites are highest risk?",
                "Show deviations for SITE-042",
                "What can you do?",
            ],
            "site_id": None,
        }
    
    # ─── 5. Protocol & Medication Rules ──────────────────────────────────
    if any(k in text_lower for k in ["protocol", "medication", "drug", "prohibited", "banned", "visit window", "phoenix"]):
        proto_md = await get_mcp_resource("trial://protocol")
        return {
            "reply": proto_md,
            "tool_used": "get_protocol_resource",
            "suggestions": [
                "Give me a trial summary",
                "Which sites are highest risk?",
                "What can you do?",
            ],
            "site_id": None,
        }
    
    # ─── 6. Deviation Classification Rule Helper ─────────────────────────
    if any(k in text_lower for k in ["classify", "is it a major", "is this a minor", "severity of"]):
        classification = await call_mcp_tool("classify_deviation", {"deviation_description": raw_text})
        return {
            "reply": classification,
            "tool_used": "classify_deviation",
            "suggestions": [
                "Give me a trial summary",
                "Show highest risk sites",
                "Show deviations for SITE-042",
            ],
            "site_id": None,
        }
    
    # ─── 7. Help & Capabilities ──────────────────────────────────────────
    if any(k in text_lower for k in ["help", "what can you do", "capabilities", "features", "hello", "hi", "hey"]):
        help_reply = (
            "🛡️ **TrialGuard Assistant Capabilities**\n\n"
            "I can assist you with real-time, deterministic clinical compliance monitoring for the **PHOENIX-301** trial over the **Model Context Protocol (MCP)**:\n\n"
            "1. **📊 Trial Overview & Status:** Ask for trial health, participant counts, and deviation distributions.\n"
            "   - *\"Give me a trial summary\"*\n"
            "   - *\"How is the trial doing?\"*\n\n"
            "2. **🏥 Site Risk Profiling:** Query composite risk scores, tiers, trends, and top risk factors.\n"
            "   - *\"What is the risk of SITE-042?\"*\n"
            "   - *\"Show highest risk sites\"*\n\n"
            "3. **⚠️ Deviation Explorer:** Inspect protocol deviations classified by ICH E6 GCP severity.\n"
            "   - *\"Show deviations for SITE-042\"*\n"
            "   - *\"What problems does SITE-001 have?\"*\n\n"
            "4. **📋 CAPA Report Generator:** Generate audit-ready Corrective and Preventive Action regulatory reports.\n"
            "   - *\"Generate CAPA for SITE-042\"*\n\n"
            "5. **📄 Protocol Specifications:** Review visit schedule tolerances, dosing thresholds, and prohibited co-medications.\n"
            "   - *\"What are the prohibited medications?\"*\n"
        )
        return {
            "reply": help_reply,
            "tool_used": None,
            "suggestions": get_default_suggestions(),
            "site_id": None,
        }
    
    # ─── 8. Specific Site mention fallback ───────────────────────────────
    if site_id:
        if not site_exists:
            return {
                "reply": f"⚠️ **Site '{site_id}' was not found** in the PHOENIX-301 trial registry.\n\nPlease check the site identifier (e.g. `SITE-001` through `SITE-210`).",
                "tool_used": None,
                "suggestions": ["Show highest risk sites", "What is the risk of SITE-042?", "Give me a trial summary"],
                "site_id": site_id,
            }
        
        site_resource = await get_mcp_resource(f"trial://sites/{site_id}")
        return {
            "reply": site_resource,
            "tool_used": "get_site_resource",
            "suggestions": [
                f"What is the risk of {site_id}?",
                f"Show deviations for {site_id}",
                f"Generate CAPA for {site_id}",
            ],
            "site_id": site_id,
        }
    
    # ─── 9. Unknown / Unmatched Query Fallback ───────────────────────────
    fallback_reply = (
        "🤔 I'm not sure how to answer that specific query, but I can help you monitor the PHOENIX-301 clinical trial.\n\n"
        "Here are common things you can ask me:\n"
        "- **Trial status:** *\"Give me a trial summary\"*\n"
        "- **Risk analysis:** *\"Which sites are highest risk?\"* or *\"Risk of SITE-042\"*\n"
        "- **Protocol deviations:** *\"Show deviations for SITE-001\"*\n"
        "- **Regulatory CAPA:** *\"Generate CAPA for SITE-042\"*\n"
        "- **Protocol rules:** *\"What are the prohibited medications?\"*"
    )
    return {
        "reply": fallback_reply,
        "tool_used": None,
        "suggestions": get_default_suggestions(),
        "site_id": None,
    }


def process_chat_message_sync(message: str) -> Dict[str, Any]:
    """Synchronous entry point for testing outside an async loop."""
    return asyncio.run(process_chat_message(message))
