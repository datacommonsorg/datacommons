# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from typing import Any

import requests


class MCPClient:
    """Client for executing Model Context Protocol (MCP) JSON-RPC tools over HTTP/SSE."""

    def __init__(
        self,
        mcp_url: str,
        auth_headers: dict[str, str] | None = None,
        timeout: int = 30,
    ):
        self.mcp_url = mcp_url.rstrip("/")
        self.timeout = timeout
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if auth_headers:
            self.headers.update(auth_headers)

    def _parse_sse_or_json(self, text: str) -> dict[str, Any]:
        """Parses SSE (event/data) or direct JSON-RPC responses."""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("data:"):
                json_str = line[len("data:") :].strip()
                return json.loads(json_str)
        return json.loads(text)

    def list_tools(self) -> list[dict[str, Any]]:
        """Lists available MCP tools via tools/list."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 1,
        }
        response = requests.post(
            self.mcp_url, json=payload, headers=self.headers, timeout=self.timeout
        )
        response.raise_for_status()
        data = self._parse_sse_or_json(response.text)
        return data.get("result", {}).get("tools", [])

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Calls an MCP tool via tools/call and returns the tool output."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": 2,
        }
        response = requests.post(
            self.mcp_url, json=payload, headers=self.headers, timeout=self.timeout
        )
        response.raise_for_status()
        data = self._parse_sse_or_json(response.text)
        return data.get("result", {})
