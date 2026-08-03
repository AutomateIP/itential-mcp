# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from fastmcp.tools import Tool

from itential_mcp.tools import command_templates


class TestToolSchemas:
    """
    Schema-assertion tests for the `devices` parameter.

    These tests inspect the actual JSON schema FastMCP generates for the
    tool, rather than only calling the tool function with a real Python
    list. Calling with a real list never exercises the generated schema,
    which is exactly why an underspecified `items: {}` schema (from a bare
    `list` annotation) previously slipped through the test suite undetected.
    """

    def test_run_command_template_devices_schema(self):
        """Test run_command_template's devices schema declares string items"""
        tool = Tool.from_function(command_templates.run_command_template)

        devices_schema = tool.parameters["properties"]["devices"]

        assert devices_schema["type"] == "array"
        assert devices_schema["items"] == {"type": "string"}
        assert devices_schema["items"] != {}
