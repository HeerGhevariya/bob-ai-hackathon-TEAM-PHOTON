"""
main.py — Entry point for the TrialGuard AI backend server.

Starts the FastAPI application via uvicorn.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import uvicorn


def main():
    """Start the TrialGuard AI backend server."""
    print("🛡️  TrialGuard AI — Clinical Trial Risk Monitor")
    print("=" * 50)
    print("Starting backend server on http://localhost:8080")
    print("API docs available at http://localhost:8080/docs")
    print("=" * 50)

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
