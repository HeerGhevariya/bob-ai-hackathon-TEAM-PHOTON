"""
mcp_client_service.py — Persistent MCP Client Service for FastAPI

Manages a persistent connection to the TrialGuard AI MCP Server (mcp_server.py)
over STDIO transport using the official Model Context Protocol (MCP) Python SDK.

Key Features:
- Persistent ClientSession across requests (no process spawning on polling)
- Automatic reconnection on process failure
- Concurrency-safe tool calling with asyncio.Lock
- Clean startup and shutdown lifecycle management for FastAPI
- Protocol-safe STDIO communication
"""

import sys
import os
import asyncio
import logging
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession

logger = logging.getLogger("mcp_client")


class McpClientManager:
    """Singleton manager for persistent MCP Client STDIO connection."""

    def __init__(self):
        self._exit_stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None
        self._lock = asyncio.Lock()
        self._connected = False
        self._server_name: str = "TrialGuard AI"
        self._discovered_tools: List[str] = []
        self._last_error: Optional[str] = None

    def _get_server_params(self) -> StdioServerParameters:
        server_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        return StdioServerParameters(
            command=sys.executable,
            args=["-u", server_path],
            env=env,
        )

    async def connect(self) -> bool:
        """Establish or re-establish persistent MCP session."""
        async with self._lock:
            if self._connected and self._session is not None:
                return True

            # Close previous stack if any
            if self._exit_stack is not None:
                try:
                    await self._exit_stack.aclose()
                except Exception:
                    pass
                self._exit_stack = None
                self._session = None

            try:
                self._exit_stack = AsyncExitStack()
                params = self._get_server_params()
                
                # Enter stdio_client context
                read_stream, write_stream = await self._exit_stack.enter_async_context(
                    stdio_client(params)
                )
                
                # Enter ClientSession context
                self._session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                
                # Perform MCP initialization handshake
                init_result = await self._session.initialize()
                if hasattr(init_result, "serverInfo") and init_result.serverInfo:
                    self._server_name = init_result.serverInfo.name or "TrialGuard AI"

                # Discover available tools
                tools_result = await self._session.list_tools()
                self._discovered_tools = [t.name for t in tools_result.tools]
                self._connected = True
                self._last_error = None
                return True

            except Exception as e:
                self._connected = False
                self._last_error = str(e)
                if self._exit_stack is not None:
                    try:
                        await self._exit_stack.aclose()
                    except Exception:
                        pass
                    self._exit_stack = None
                self._session = None
                return False

    async def disconnect(self):
        """Close persistent MCP session and terminate subprocess."""
        async with self._lock:
            self._connected = False
            if self._exit_stack is not None:
                try:
                    await self._exit_stack.aclose()
                except Exception:
                    pass
                self._exit_stack = None
            self._session = None

    async def get_status(self) -> Dict[str, Any]:
        """Return live health status of the MCP connection."""
        if not self._connected or self._session is None:
            # Try connecting if not connected
            connected = await self.connect()
            if not connected:
                return {
                    "connected": False,
                    "server_name": self._server_name,
                    "transport": "stdio",
                    "tools": [],
                    "error": self._last_error or "MCP server not connected",
                }

        return {
            "connected": True,
            "server_name": self._server_name,
            "transport": "stdio",
            "tools": self._discovered_tools,
        }

    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        """Execute an MCP tool over the persistent MCP session."""
        if not self._connected or self._session is None:
            connected = await self.connect()
            if not connected:
                return f"⚠️ **MCP Error:** MCP server is offline. Cannot execute tool `{tool_name}`.\n\n*Error:* {self._last_error}"

        async with self._lock:
            try:
                assert self._session is not None
                result = await self._session.call_tool(tool_name, arguments=arguments or {})
                
                texts = []
                for block in result.content:
                    if hasattr(block, "text"):
                        texts.append(block.text)
                    elif isinstance(block, dict) and "text" in block:
                        texts.append(block["text"])
                    else:
                        texts.append(str(block))
                return "\n".join(texts)

            except Exception as e:
                # Connection might have dropped, mark disconnected
                self._connected = False
                self._last_error = str(e)
                return f"⚠️ **MCP Protocol Error:** Tool `{tool_name}` failed during execution.\n\n*Details:* {e}"

    async def read_resource(self, uri: str) -> str:
        """Read an MCP resource over the persistent MCP session."""
        if not self._connected or self._session is None:
            connected = await self.connect()
            if not connected:
                return f"⚠️ **MCP Error:** MCP server is offline. Cannot read resource `{uri}`."

        async with self._lock:
            try:
                assert self._session is not None
                result = await self._session.read_resource(uri)
                texts = []
                for content in result.contents:
                    if hasattr(content, "text"):
                        texts.append(content.text)
                    elif isinstance(content, dict) and "text" in content:
                        texts.append(content["text"])
                    else:
                        texts.append(str(content))
                return "\n".join(texts)
            except Exception as e:
                self._connected = False
                self._last_error = str(e)
                return f"⚠️ **MCP Protocol Error:** Failed to read resource `{uri}`.\n\n*Details:* {e}"


# Singleton client instance
_mcp_manager = McpClientManager()


def get_mcp_manager() -> McpClientManager:
    """Get the global McpClientManager instance."""
    return _mcp_manager


async def get_mcp_status() -> Dict[str, Any]:
    """Helper to get live MCP status."""
    return await _mcp_manager.get_status()


async def call_mcp_tool(tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
    """Helper to call an MCP tool."""
    return await _mcp_manager.call_tool(tool_name, arguments)


async def get_mcp_resource(uri: str) -> str:
    """Helper to read an MCP resource."""
    return await _mcp_manager.read_resource(uri)
