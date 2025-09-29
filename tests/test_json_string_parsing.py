# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from fastmcp import Context

from itential_mcp.bindings import service, endpoint
from itential_mcp import client


class TestServiceJSONStringParsing:
    """Test cases for service binding JSON string parameter parsing"""

    @pytest.fixture
    def mock_context(self):
        """Create a mock FastMCP context"""
        context = MagicMock(spec=Context)
        platform_client = AsyncMock(spec=client.PlatformClient)
        platform_client.gateway_manager = AsyncMock()
        context.request_context.lifespan_context.get.return_value = platform_client
        return context

    @pytest.fixture
    def mock_tool_config(self):
        """Create a mock tool configuration"""
        @dataclass
        class MockTool:
            name: str = "test-service"
            tool_name: str = "test_tool"
        
        return MockTool()

    @pytest.mark.asyncio
    async def test_run_service_with_json_string_input_params(self, mock_context, mock_tool_config):
        """Test service execution with JSON string input_params (Claude Desktop format)"""
        mock_service = {
            "service_metadata": {
                "name": "test-service",
                "location": "cluster-1"
            }
        }
        
        platform_client = mock_context.request_context.lifespan_context.get.return_value
        platform_client.gateway_manager.get_services.return_value = [mock_service]
        
        # JSON string format (as sent by Claude Desktop)
        json_string_params = '{"op": "list", "region": "us-west-1", "format": "json"}'
        expected_parsed_params = {"op": "list", "region": "us-west-1", "format": "json"}
        
        with patch('itential_mcp.bindings.service.gateway_manager.run_service') as mock_run:
            await service.run_service(
                mock_context,
                _tool_config=mock_tool_config,
                input_params=json_string_params
            )
            
            # Verify the JSON string was parsed to dict
            mock_run.assert_called_once_with(
                mock_context,
                name="test-service",
                cluster="cluster-1",
                input_params=expected_parsed_params
            )

    @pytest.mark.asyncio
    async def test_run_service_with_dict_input_params(self, mock_context, mock_tool_config):
        """Test service execution with dict input_params (CLI format)"""
        mock_service = {
            "service_metadata": {
                "name": "test-service",
                "location": "cluster-1"
            }
        }
        
        platform_client = mock_context.request_context.lifespan_context.get.return_value
        platform_client.gateway_manager.get_services.return_value = [mock_service]
        
        # Dict format (as sent by CLI)
        dict_params = {"op": "list", "region": "us-west-1", "format": "json"}
        
        with patch('itential_mcp.bindings.service.gateway_manager.run_service') as mock_run:
            await service.run_service(
                mock_context,
                _tool_config=mock_tool_config,
                input_params=dict_params
            )
            
            # Verify the dict was passed through unchanged
            mock_run.assert_called_once_with(
                mock_context,
                name="test-service",
                cluster="cluster-1",
                input_params=dict_params
            )

    @pytest.mark.asyncio
    async def test_run_service_with_invalid_json_string(self, mock_context, mock_tool_config):
        """Test service execution with invalid JSON string gracefully handles error"""
        mock_service = {
            "service_metadata": {
                "name": "test-service",
                "location": "cluster-1"
            }
        }
        
        platform_client = mock_context.request_context.lifespan_context.get.return_value
        platform_client.gateway_manager.get_services.return_value = [mock_service]
        
        # Invalid JSON string
        invalid_json_string = '{"op": "list", "region": invalid}'
        
        with patch('itential_mcp.bindings.service.gateway_manager.run_service') as mock_run:
            await service.run_service(
                mock_context,
                _tool_config=mock_tool_config,
                input_params=invalid_json_string
            )
            
            # Verify invalid JSON resulted in None
            mock_run.assert_called_once_with(
                mock_context,
                name="test-service",
                cluster="cluster-1",
                input_params=None
            )


class TestEndpointJSONStringParsing:
    """Test cases for endpoint binding JSON string parameter parsing"""

    @pytest.fixture
    def mock_context(self):
        """Create a mock FastMCP context"""
        context = MagicMock(spec=Context)
        platform_client = AsyncMock(spec=client.PlatformClient)
        context.request_context.lifespan_context.get.return_value = platform_client
        return context

    @pytest.fixture
    def mock_tool_config(self):
        """Create a mock endpoint tool configuration"""
        @dataclass
        class MockTool:
            automation: str = "test-automation"
            name: str = "test-trigger"
        
        return MockTool()

    @pytest.mark.asyncio
    @patch('itential_mcp.bindings.endpoint._get_trigger')
    @patch('itential_mcp.bindings.endpoint.operations_manager.start_workflow')
    async def test_start_workflow_with_json_string_data(
        self, mock_start_workflow, mock_get_trigger, mock_context, mock_tool_config
    ):
        """Test workflow execution with JSON string data (Claude Desktop format)"""
        mock_trigger = {"routeName": "test-route"}
        mock_get_trigger.return_value = mock_trigger
        
        # JSON string format (as sent by Claude Desktop)
        json_string_data = '{"interface": "250", "networkName": "MCP_DEMO", "deviceName": "IOS-CSR-AWS-1"}'
        expected_parsed_data = {"interface": "250", "networkName": "MCP_DEMO", "deviceName": "IOS-CSR-AWS-1"}
        
        await endpoint.start_workflow(
            mock_context,
            _tool_config=mock_tool_config,
            data=json_string_data
        )
        
        # Verify the JSON string was parsed to dict
        mock_start_workflow.assert_called_once_with(
            mock_context,
            route_name="test-route",
            data=expected_parsed_data
        )

    @pytest.mark.asyncio
    @patch('itential_mcp.bindings.endpoint._get_trigger')
    @patch('itential_mcp.bindings.endpoint.operations_manager.start_workflow')
    async def test_start_workflow_with_dict_data(
        self, mock_start_workflow, mock_get_trigger, mock_context, mock_tool_config
    ):
        """Test workflow execution with dict data (CLI format)"""
        mock_trigger = {"routeName": "test-route"}
        mock_get_trigger.return_value = mock_trigger
        
        # Dict format (as sent by CLI)
        dict_data = {"interface": "250", "networkName": "MCP_DEMO", "deviceName": "IOS-CSR-AWS-1"}
        
        await endpoint.start_workflow(
            mock_context,
            _tool_config=mock_tool_config,
            data=dict_data
        )
        
        # Verify the dict was passed through unchanged
        mock_start_workflow.assert_called_once_with(
            mock_context,
            route_name="test-route",
            data=dict_data
        )

    @pytest.mark.asyncio
    @patch('itential_mcp.bindings.endpoint._get_trigger')
    @patch('itential_mcp.bindings.endpoint.operations_manager.start_workflow')
    async def test_start_workflow_with_invalid_json_string(
        self, mock_start_workflow, mock_get_trigger, mock_context, mock_tool_config
    ):
        """Test workflow execution with invalid JSON string gracefully handles error"""
        mock_trigger = {"routeName": "test-route"}
        mock_get_trigger.return_value = mock_trigger
        
        # Invalid JSON string
        invalid_json_string = '{"interface": "250", "networkName": invalid}'
        
        await endpoint.start_workflow(
            mock_context,
            _tool_config=mock_tool_config,
            data=invalid_json_string
        )
        
        # Verify invalid JSON resulted in None
        mock_start_workflow.assert_called_once_with(
            mock_context,
            route_name="test-route",
            data=None
        )
