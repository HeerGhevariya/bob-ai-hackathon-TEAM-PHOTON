"""
watsonx_client.py — IBM watsonx.ai Client for LLM-Enhanced CAPA Reports

Provides an optional LLM layer that enhances template-based CAPA reports
with richer narrative analysis. Falls back gracefully if watsonx.ai is
not configured (missing API key) — the template engine always works.

Architecture:
    [Template Engine] → base CAPA report
    [watsonx.ai LLM]  → enhanced executive summary, root cause narrative,
                         and contextual recommendations

The LLM never decides what counts as a deviation or how severe it is.
It only enriches the human-readable narrative around findings that the
deterministic engine has already identified and classified.
"""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


_client = None
_is_available: Optional[bool] = None


def is_watsonx_configured() -> bool:
    """Check if watsonx.ai credentials are available."""
    return bool(
        os.getenv("WATSONX_API_KEY")
        and os.getenv("WATSONX_PROJECT_ID")
    )


def get_watsonx_client():
    """
    Get the watsonx.ai client singleton.
    Returns None if not configured.
    """
    global _client, _is_available

    if _is_available is False:
        return None

    if _client is not None:
        return _client

    if not is_watsonx_configured():
        _is_available = False
        return None

    try:
        from ibm_watsonx_ai.foundation_models import ModelInference
        from ibm_watsonx_ai import Credentials

        api_key = os.getenv("WATSONX_API_KEY")
        project_id = os.getenv("WATSONX_PROJECT_ID")
        url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

        credentials = Credentials(
            url=url,
            api_key=api_key,
        )

        _client = ModelInference(
            model_id="ibm/granite-3-8b-instruct",
            credentials=credentials,
            project_id=project_id,
            params={
                "max_new_tokens": 1024,
                "temperature": 0.3,
                "top_p": 0.9,
                "repetition_penalty": 1.1,
            },
        )

        _is_available = True
        print("🤖 watsonx.ai connected — LLM-enhanced CAPA reports enabled")
        return _client

    except ImportError:
        print("⚠️  ibm-watsonx-ai not installed. Install with: pip install ibm-watsonx-ai")
        _is_available = False
        return None
    except Exception as e:
        print(f"⚠️  watsonx.ai initialization failed: {e}")
        _is_available = False
        return None


def generate_text(prompt: str) -> Optional[str]:
    """
    Generate text using watsonx.ai.
    Returns None if watsonx is not available.
    """
    client = get_watsonx_client()
    if not client:
        return None

    try:
        response = client.generate_text(prompt=prompt)
        return response.strip() if response else None
    except Exception as e:
        print(f"⚠️  watsonx.ai generation failed: {e}")
        return None


def enhance_executive_summary(
    site_id: str,
    site_name: str,
    template_summary: str,
    severity_breakdown: dict,
    deviation_types: dict,
    risk_score: float = 0,
    risk_tier: str = "unknown",
    trend: str = "stable",
) -> str:
    """
    Enhance a template-based executive summary with LLM-generated narrative.
    Falls back to the template summary if watsonx is unavailable.
    """
    prompt = f"""You are a clinical trial regulatory affairs specialist writing a CAPA report executive summary.

Based on the following findings for site {site_id} ({site_name}), write a concise 3-4 sentence executive summary suitable for a regulatory submission. Use professional, formal language. Reference ICH E6(R2) GCP guidelines.

FINDINGS:
- Severity breakdown: {severity_breakdown}
- Deviation types: {deviation_types}
- Risk score: {risk_score}/100 ({risk_tier})
- Trend: {trend}

TEMPLATE SUMMARY (use as a starting point, enhance with regulatory context):
{template_summary}

Write ONLY the enhanced executive summary, nothing else:"""

    result = generate_text(prompt)
    return result if result else template_summary


def enhance_root_cause_analysis(
    template_root_cause: str,
    deviation_descriptions: list[str],
    contributing_factors: list[str],
) -> str:
    """
    Enhance template-based root cause analysis with LLM-generated narrative.
    Falls back to the template analysis if watsonx is unavailable.
    """
    deviations_text = "\n".join(f"- {d}" for d in deviation_descriptions[:10])

    prompt = f"""You are a clinical trial quality assurance expert conducting root cause analysis for a CAPA report.

Based on the following protocol deviations, write a professional root cause analysis paragraph (4-6 sentences). Reference ICH E6(R2) requirements. Identify systemic vs. individual factors.

DEVIATIONS FOUND:
{deviations_text}

IDENTIFIED CONTRIBUTING FACTORS:
{', '.join(contributing_factors)}

TEMPLATE ANALYSIS (enhance with deeper regulatory context):
{template_root_cause}

Write ONLY the enhanced root cause analysis, nothing else:"""

    result = generate_text(prompt)
    return result if result else template_root_cause


def generate_llm_recommendations(
    site_id: str,
    deviation_types: dict,
    severity_breakdown: dict,
    risk_score: float,
) -> Optional[str]:
    """
    Generate additional LLM-powered recommendations beyond template actions.
    Returns None if watsonx is unavailable.
    """
    prompt = f"""You are a clinical trial regulatory affairs specialist providing additional recommendations for a CAPA report.

Site {site_id} has the following profile:
- Deviation types: {deviation_types}
- Severity: {severity_breakdown}
- Risk score: {risk_score}/100

Provide 3 specific, actionable additional recommendations that go beyond standard corrective actions. Focus on systemic improvements, process redesign, or technology solutions. Format as a numbered list.

Additional recommendations:"""

    return generate_text(prompt)
