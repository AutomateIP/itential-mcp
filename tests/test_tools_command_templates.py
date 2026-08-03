# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastmcp import Context
from fastmcp.tools import Tool

from itential_mcp.models.command_templates import DescribeCommandTemplateResponse
from itential_mcp.tools import command_templates


class TestDescribeCommandTemplate:
    """Tests for the describe_command_template tool function"""

    @pytest.fixture
    def mock_context(self):
        """Create a mock Context object"""
        context = AsyncMock(spec=Context)
        context.debug = AsyncMock()

        mock_client = MagicMock()
        context.request_context = MagicMock()
        context.request_context.lifespan_context = MagicMock()
        context.request_context.lifespan_context.get.return_value = mock_client

        return context

    @pytest.mark.asyncio
    async def test_describe_command_template_includes_description(self, mock_context):
        """Test describe_command_template surfaces the description field
        from the platform response, guarding against the silent data loss
        that occurred when CommandTemplateDetail had no description field
        declared.
        """
        mock_data = {
            "_id": "linux-curl-http",
            "name": "linux-curl-http",
            "description": "Runs curl against the device",
            "commands": [{"command": "show version", "rules": []}],
            "namespace": None,
            "passRule": True,
        }

        mock_client = mock_context.request_context.lifespan_context.get.return_value
        mock_client.mop = MagicMock()
        mock_client.mop.describe_command_template = AsyncMock(return_value=mock_data)

        result = await command_templates.describe_command_template(
            mock_context, name="linux-curl-http", project=None
        )

        mock_client.mop.describe_command_template.assert_called_once_with(
            name="linux-curl-http", project=None
        )

        assert isinstance(result, DescribeCommandTemplateResponse)
        assert result.template.description == "Runs curl against the device"

    @pytest.mark.asyncio
    async def test_describe_command_template_missing_description(self, mock_context):
        """Test describe_command_template defaults description to None when
        the platform response does not include the key.
        """
        mock_data = {
            "_id": "linux-curl-http",
            "name": "linux-curl-http",
            "commands": [],
            "namespace": None,
            "passRule": True,
        }

        mock_client = mock_context.request_context.lifespan_context.get.return_value
        mock_client.mop = MagicMock()
        mock_client.mop.describe_command_template = AsyncMock(return_value=mock_data)

        result = await command_templates.describe_command_template(
            mock_context, name="linux-curl-http", project=None
        )

        assert result.template.description is None


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
