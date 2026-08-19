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


import pytest

from tests.integration.core.config_schema import MCPToolCallSpec, TestManifest
from tests.integration.core.mcp_client import MCPClient


class TestMCPTools:
    """Validates Model Context Protocol (MCP) tool execution against the live testbed."""

    def test_mcp_list_tools(
        self, seeded_testbed, mcp_client: MCPClient, test_manifest: TestManifest
    ):
        """Verifies that MCP server exposes standard Data Commons tools."""
        if not test_manifest.stages.mcp_agent:
            pytest.skip("MCP Agent stage disabled in test manifest.")

        tools = mcp_client.list_tools()
        assert len(tools) > 0, "Expected non-empty list of MCP tools"
        tool_names = [t.get("name") for t in tools]
        assert "search_indicators" in tool_names, (
            f"Expected 'search_indicators' in tools: {tool_names}"
        )

    def test_mcp_tool_call(
        self,
        seeded_testbed,
        mcp_client: MCPClient,
        mcp_tool_spec: MCPToolCallSpec | None,
    ):
        """Tests calling declared MCP tool with arguments."""
        if not mcp_tool_spec:
            pytest.skip(
                "MCP Agent stage disabled or no tool calls declared in manifest."
            )

        result = mcp_client.call_tool(mcp_tool_spec.tool_name, mcp_tool_spec.arguments)
        assert "content" in result, f"Expected 'content' in tool result, got: {result}"

        text_content = result["content"][0]["text"]
        for expected_dcid in mcp_tool_spec.expected_match_dcids:
            assert expected_dcid in text_content, (
                f"Tool '{mcp_tool_spec.tool_name}' result did not contain expected DCID '{expected_dcid}': {text_content[:300]}"
            )
