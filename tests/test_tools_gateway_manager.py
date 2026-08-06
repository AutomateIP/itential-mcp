# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastmcp import Context
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)

from itential_mcp.tools.gateway_manager import (
    get_services,
    get_gateways,
    run_service,
    export_gateway_configuration,
    import_gateway_configuration,
    _export_contains_sensitive_data,
)
from itential_mcp.models.gateway_manager import (
    ServiceElement,
    GetServicesResponse,
    GatewayElement,
    GetGatewaysResponse,
    RunServiceResponse,
    ExportGatewayConfigurationResponse,
    ImportGatewayConfigurationResponse,
)
from itential_mcp.core.exceptions import AuthorizationException, ValidationException


class TestGatewayManagerTools:
    """Test cases for Gateway Manager tool functions."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_context = AsyncMock(spec=Context)
        self.mock_context.debug = AsyncMock()

        # Create mock client
        self.mock_client = MagicMock()
        self.mock_gateway_manager_service = MagicMock()

        # Set up async methods on gateway manager service
        self.mock_gateway_manager_service.get_services = AsyncMock()
        self.mock_gateway_manager_service.get_gateways = AsyncMock()
        self.mock_gateway_manager_service.run_service = AsyncMock()
        self.mock_gateway_manager_service.export_configuration = AsyncMock()
        self.mock_gateway_manager_service.import_configuration = AsyncMock()

        # Attach gateway manager service to client
        self.mock_client.gateway_manager = self.mock_gateway_manager_service

        # Set up context to return the mock client
        self.mock_context.request_context.lifespan_context.get.return_value = (
            self.mock_client
        )


class TestGetServices(TestGatewayManagerTools):
    """Test cases for get_services function."""

    def test_get_services_function_exists(self):
        """Test that get_services function exists and is callable."""
        assert callable(get_services)

    def create_mock_services_data(self):
        """Create mock services data for testing."""
        return [
            {
                "service_metadata": {
                    "name": "backup-service",
                    "location": "cluster-east",
                    "type": "ansible-playbook",
                    "description": "Automated backup service",
                    "decorator": {
                        "type": "object",
                        "properties": {
                            "backup_path": {"type": "string"},
                            "retention_days": {"type": "integer", "default": 7},
                        },
                        "required": ["backup_path"],
                    },
                }
            },
            {
                "service_metadata": {
                    "name": "deploy-service",
                    "location": "cluster-west",
                    "type": "python-script",
                    "description": "Application deployment service",
                    "decorator": {
                        "type": "object",
                        "properties": {
                            "app_name": {"type": "string"},
                            "version": {"type": "string"},
                            "environment": {
                                "type": "string",
                                "enum": ["dev", "staging", "prod"],
                            },
                        },
                        "required": ["app_name", "version", "environment"],
                    },
                }
            },
            {
                "service_metadata": {
                    "name": "infrastructure-service",
                    "location": "cluster-central",
                    "type": "opentofu-plan",
                    "description": "Infrastructure provisioning service",
                    "decorator": {
                        "type": "object",
                        "properties": {
                            "terraform_config": {"type": "string"},
                            "apply": {"type": "boolean", "default": False},
                        },
                    },
                }
            },
        ]

    @pytest.mark.asyncio
    async def test_get_services_success(self):
        """Test successful retrieval of services."""
        mock_data = self.create_mock_services_data()
        self.mock_client.gateway_manager.get_services.return_value = mock_data

        result = await get_services(self.mock_context)

        # Verify context info was called
        self.mock_context.debug.assert_called_once_with("inside get_services(...)")

        # Verify client method was called
        self.mock_client.gateway_manager.get_services.assert_called_once()

        # Verify result type and content
        assert isinstance(result, GetServicesResponse)
        assert len(result.root) == 3

        # Verify first service
        service1 = result.root[0]
        assert isinstance(service1, ServiceElement)
        assert service1.name == "backup-service"
        assert service1.cluster == "cluster-east"
        assert service1.type == "ansible-playbook"
        assert service1.description == "Automated backup service"
        assert service1.decorator["required"] == ["backup_path"]

        # Verify second service
        service2 = result.root[1]
        assert service2.name == "deploy-service"
        assert service2.cluster == "cluster-west"
        assert service2.type == "python-script"

        # Verify third service
        service3 = result.root[2]
        assert service3.name == "infrastructure-service"
        assert service3.type == "opentofu-plan"

    @pytest.mark.asyncio
    async def test_get_services_empty_result(self):
        """Test get_services with empty result."""
        mock_data = []
        self.mock_client.gateway_manager.get_services.return_value = mock_data

        result = await get_services(self.mock_context)

        assert isinstance(result, GetServicesResponse)
        assert len(result.root) == 0

    @pytest.mark.asyncio
    async def test_get_services_single_service(self):
        """Test get_services with single service."""
        mock_data = [
            {
                "service_metadata": {
                    "name": "single-service",
                    "location": "single-cluster",
                    "type": "custom-script",
                    "description": "Single service test",
                    "decorator": {},
                }
            }
        ]
        self.mock_client.gateway_manager.get_services.return_value = mock_data

        result = await get_services(self.mock_context)

        assert isinstance(result, GetServicesResponse)
        assert len(result.root) == 1
        assert result.root[0].name == "single-service"

    @pytest.mark.asyncio
    async def test_get_services_with_complex_decorators(self):
        """Test get_services with complex decorator schemas."""
        mock_data = [
            {
                "service_metadata": {
                    "name": "complex-service",
                    "location": "complex-cluster",
                    "type": "ansible-playbook",
                    "description": "Service with complex decorator",
                    "decorator": {
                        "type": "object",
                        "properties": {
                            "config": {
                                "type": "object",
                                "properties": {
                                    "timeout": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 3600,
                                    },
                                    "retries": {"type": "integer", "default": 3},
                                },
                            },
                            "hosts": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 1,
                            },
                            "variables": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["hosts"],
                    },
                }
            }
        ]
        self.mock_client.gateway_manager.get_services.return_value = mock_data

        result = await get_services(self.mock_context)

        assert isinstance(result, GetServicesResponse)
        assert len(result.root) == 1
        service = result.root[0]
        assert service.name == "complex-service"
        assert "config" in service.decorator["properties"]
        assert "hosts" in service.decorator["properties"]

    @pytest.mark.asyncio
    async def test_get_services_client_error(self):
        """Test get_services when client raises an exception."""
        self.mock_client.gateway_manager.get_services.side_effect = Exception(
            "Gateway Manager connection failed"
        )

        with pytest.raises(Exception, match="Gateway Manager connection failed"):
            await get_services(self.mock_context)

        # Verify context info was still called
        self.mock_context.debug.assert_called_once_with("inside get_services(...)")


class TestGetGateways(TestGatewayManagerTools):
    """Test cases for get_gateways function."""

    def test_get_gateways_function_exists(self):
        """Test that get_gateways function exists and is callable."""
        assert callable(get_gateways)

    def create_mock_gateways_data(self):
        """Create mock gateways data for testing."""
        return {
            "results": [
                {
                    "gateway_name": "production-gateway",
                    "cluster_id": "prod-cluster-01",
                    "description": "Production environment gateway",
                    "connection_status": "connected",
                    "enabled": True,
                },
                {
                    "gateway_name": "staging-gateway",
                    "cluster_id": "staging-cluster-01",
                    "description": "Staging environment gateway",
                    "connection_status": "disconnected",
                    "enabled": True,
                },
                {
                    "gateway_name": "development-gateway",
                    "cluster_id": "dev-cluster-01",
                    "description": "Development environment gateway",
                    "connection_status": "connecting",
                    "enabled": False,
                },
                {
                    "gateway_name": "test-gateway",
                    "cluster_id": "test-cluster-01",
                    "description": "Test environment gateway",
                    "connection_status": "error",
                    "enabled": True,
                },
            ]
        }

    @pytest.mark.asyncio
    async def test_get_gateways_success(self):
        """Test successful retrieval of gateways."""
        mock_data = self.create_mock_gateways_data()
        self.mock_gateway_manager_service.get_gateways.return_value = mock_data

        result = await get_gateways(self.mock_context)

        # Verify context info was called
        self.mock_context.debug.assert_called_once_with("inside get_gateways(...)")

        # Verify client method was called
        self.mock_gateway_manager_service.get_gateways.assert_called_once()

        # Verify result type and content - only connected gateways are returned
        assert isinstance(result, GetGatewaysResponse)
        assert len(result.root) == 1

        # Verify only the connected gateway is returned
        gateway1 = result.root[0]
        assert isinstance(gateway1, GatewayElement)
        assert gateway1.name == "production-gateway"
        assert gateway1.cluster == "prod-cluster-01"
        assert gateway1.description == "Production environment gateway"
        assert gateway1.status == "connected"
        assert gateway1.enabled is True

    @pytest.mark.asyncio
    async def test_get_gateways_empty_result(self):
        """Test get_gateways with empty result."""
        mock_data = {"results": []}
        self.mock_gateway_manager_service.get_gateways.return_value = mock_data

        result = await get_gateways(self.mock_context)

        assert isinstance(result, GetGatewaysResponse)
        assert len(result.root) == 0

    @pytest.mark.asyncio
    async def test_get_gateways_single_gateway(self):
        """Test get_gateways with single gateway."""
        mock_data = {
            "results": [
                {
                    "gateway_name": "solo-gateway",
                    "cluster_id": "solo-cluster",
                    "description": "Single gateway test",
                    "connection_status": "connected",
                    "enabled": True,
                }
            ]
        }
        self.mock_gateway_manager_service.get_gateways.return_value = mock_data

        result = await get_gateways(self.mock_context)

        assert isinstance(result, GetGatewaysResponse)
        assert len(result.root) == 1
        assert result.root[0].name == "solo-gateway"

    @pytest.mark.asyncio
    async def test_get_gateways_various_statuses(self):
        """Test get_gateways filters to only return connected gateways."""
        mock_data = {
            "results": [
                {
                    "gateway_name": "connected-gw",
                    "cluster_id": "cluster-1",
                    "description": "Connected gateway",
                    "connection_status": "connected",
                    "enabled": True,
                },
                {
                    "gateway_name": "disconnected-gw",
                    "cluster_id": "cluster-2",
                    "description": "Disconnected gateway",
                    "connection_status": "disconnected",
                    "enabled": False,
                },
                {
                    "gateway_name": "error-gw",
                    "cluster_id": "cluster-3",
                    "description": "Gateway with error",
                    "connection_status": "error",
                    "enabled": True,
                },
            ]
        }
        self.mock_gateway_manager_service.get_gateways.return_value = mock_data

        result = await get_gateways(self.mock_context)

        assert isinstance(result, GetGatewaysResponse)
        assert len(result.root) == 1

        # Only connected gateways should be returned
        assert result.root[0].status == "connected"
        assert result.root[0].name == "connected-gw"

    @pytest.mark.asyncio
    async def test_get_gateways_client_error(self):
        """Test get_gateways when client raises an exception."""
        self.mock_gateway_manager_service.get_gateways.side_effect = Exception(
            "Failed to fetch gateways"
        )

        with pytest.raises(Exception, match="Failed to fetch gateways"):
            await get_gateways(self.mock_context)

        # Verify context info was still called
        self.mock_context.debug.assert_called_once_with("inside get_gateways(...)")


class TestRunService(TestGatewayManagerTools):
    """Test cases for run_service function."""

    def test_run_service_function_exists(self):
        """Test that run_service function exists and is callable."""
        assert callable(run_service)

    def create_mock_run_service_success_data(self):
        """Create mock successful run service data."""
        return {
            "result": {
                "stdout": json.dumps(
                    {"status": "success", "message": "Service executed successfully"}
                ),
                "stderr": "",
                "return_code": 0,
                "start_time": "2025-01-22T10:00:00.000Z",
                "end_time": "2025-01-22T10:00:05.500Z",
                "elapsed_time": 5.5,
            }
        }

    def create_mock_run_service_json_stdout_data(self):
        """Create mock run service data with JSON stdout."""
        json_output = {"status": "success", "processed_items": 42, "warnings": []}
        return {
            "result": {
                "stdout": json.dumps(json_output),
                "stderr": "Info: Processing completed",
                "return_code": 0,
                "start_time": "2025-01-22T10:00:00.000Z",
                "end_time": "2025-01-22T10:00:02.250Z",
                "elapsed_time": 2.25,
            }
        }

    def create_mock_run_service_error_data(self):
        """Create mock error run service data."""
        return {
            "error": {
                "data": "Service execution failed: Connection timeout to target host"
            }
        }

    @pytest.mark.asyncio
    async def test_run_service_success_basic(self):
        """Test successful service run with basic output."""
        mock_data = self.create_mock_run_service_success_data()
        self.mock_client.gateway_manager.run_service.return_value = mock_data

        result = await run_service(
            self.mock_context,
            name="test-service",
            cluster="test-cluster",
            input_params={"param1": "value1"},
        )

        # Verify context info was called
        self.mock_context.debug.assert_called_once_with("inside run_service(...)")

        # Verify client method was called with correct parameters
        self.mock_client.gateway_manager.run_service.assert_called_once_with(
            "test-service", "test-cluster", input_params={"param1": "value1"}
        )

        # Verify result type and content
        assert isinstance(result, RunServiceResponse)
        # stdout should be parsed as JSON object
        assert isinstance(result.stdout, dict)
        assert result.stdout["status"] == "success"
        assert result.stdout["message"] == "Service executed successfully"
        assert result.stderr == ""
        assert result.return_code == 0
        assert result.start_time == "2025-01-22T10:00:00.000Z"
        assert result.end_time == "2025-01-22T10:00:05.500Z"
        assert result.elapsed_time == 5.5

    @pytest.mark.asyncio
    async def test_run_service_success_no_params(self):
        """Test successful service run without input parameters."""
        mock_data = self.create_mock_run_service_success_data()
        self.mock_client.gateway_manager.run_service.return_value = mock_data

        result = await run_service(
            self.mock_context,
            name="no-param-service",
            cluster="test-cluster",
            input_params=None,
        )

        # Verify client method was called with None for input_params
        self.mock_client.gateway_manager.run_service.assert_called_once_with(
            "no-param-service", "test-cluster", input_params=None
        )

        assert isinstance(result, RunServiceResponse)
        # stdout should be parsed as JSON
        assert isinstance(result.stdout, dict)
        assert result.stdout["status"] == "success"
        assert result.return_code == 0

    @pytest.mark.asyncio
    async def test_run_service_with_json_stdout_parsing(self):
        """Test service run with JSON stdout that gets parsed."""
        mock_data = self.create_mock_run_service_json_stdout_data()
        self.mock_client.gateway_manager.run_service.return_value = mock_data

        result = await run_service(
            self.mock_context,
            name="json-service",
            cluster="json-cluster",
            input_params={"format": "json"},
        )

        # Verify client method was called
        self.mock_client.gateway_manager.run_service.assert_called_once_with(
            "json-service", "json-cluster", input_params={"format": "json"}
        )

        # Verify result
        assert isinstance(result, RunServiceResponse)

        # stdout should be parsed as JSON object, not string
        assert isinstance(result.stdout, dict)
        assert result.stdout["status"] == "success"
        assert result.stdout["processed_items"] == 42
        assert result.stdout["warnings"] == []

        assert result.stderr == "Info: Processing completed"
        assert result.return_code == 0
        assert result.elapsed_time == 2.25

    @pytest.mark.asyncio
    async def test_run_service_with_invalid_json_stdout(self):
        """Test service run with invalid JSON stdout (should not be parsed)."""
        mock_data = {
            "result": {
                "stdout": "Invalid JSON: {incomplete",
                "stderr": "",
                "return_code": 0,
                "start_time": "2025-01-22T10:00:00.000Z",
                "end_time": "2025-01-22T10:00:01.000Z",
                "elapsed_time": 1.0,
            }
        }
        self.mock_client.gateway_manager.run_service.return_value = mock_data

        result = await run_service(
            self.mock_context,
            name="invalid-json-service",
            cluster="test-cluster",
            input_params=None,
        )

        # stdout should remain as string since JSON parsing failed
        assert isinstance(result.stdout, str)
        assert result.stdout == "Invalid JSON: {incomplete"

    @pytest.mark.asyncio
    async def test_run_service_error_response(self):
        """Test service run that returns an error."""
        mock_data = self.create_mock_run_service_error_data()
        self.mock_client.gateway_manager.run_service.return_value = mock_data

        with pytest.raises(
            ValueError,
            match="Service execution failed: Connection timeout to target host",
        ):
            await run_service(
                self.mock_context,
                name="failing-service",
                cluster="test-cluster",
                input_params={"timeout": 30},
            )

        # Verify client method was still called
        self.mock_client.gateway_manager.run_service.assert_called_once_with(
            "failing-service", "test-cluster", input_params={"timeout": 30}
        )

    @pytest.mark.asyncio
    async def test_run_service_with_failure_return_code(self):
        """Test service run that completes but returns non-zero exit code."""
        mock_data = {
            "result": {
                "stdout": json.dumps(
                    {"status": "partial_failure", "errors": ["non-critical errors"]}
                ),
                "stderr": "Warning: Some operations failed\nError: Critical component unavailable",
                "return_code": 1,
                "start_time": "2025-01-22T10:00:00.000Z",
                "end_time": "2025-01-22T10:00:15.000Z",
                "elapsed_time": 15.0,
            }
        }
        self.mock_client.gateway_manager.run_service.return_value = mock_data

        result = await run_service(
            self.mock_context,
            name="partial-failure-service",
            cluster="test-cluster",
            input_params=None,
        )

        assert isinstance(result, RunServiceResponse)
        assert result.return_code == 1
        # stdout should be parsed as JSON
        assert isinstance(result.stdout, dict)
        assert result.stdout["status"] == "partial_failure"
        assert "non-critical errors" in result.stdout["errors"]
        assert "Critical component unavailable" in result.stderr
        assert result.elapsed_time == 15.0

    @pytest.mark.asyncio
    async def test_run_service_with_complex_parameters(self):
        """Test service run with complex input parameters."""
        complex_params = {
            "configuration": {"timeout": 300, "retry_count": 3, "parallel_jobs": 5},
            "targets": ["host1.example.com", "host2.example.com"],
            "options": {"verbose": True, "dry_run": False, "backup_before": True},
            "metadata": {"user": "automation", "reason": "scheduled_maintenance"},
        }

        mock_data = self.create_mock_run_service_success_data()
        self.mock_client.gateway_manager.run_service.return_value = mock_data

        result = await run_service(
            self.mock_context,
            name="complex-service",
            cluster="production-cluster",
            input_params=complex_params,
        )

        # Verify client was called with complex parameters
        self.mock_client.gateway_manager.run_service.assert_called_once_with(
            "complex-service", "production-cluster", input_params=complex_params
        )

        assert isinstance(result, RunServiceResponse)
        # stdout should be parsed as JSON
        assert isinstance(result.stdout, dict)
        assert result.stdout["status"] == "success"
        assert result.return_code == 0

    @pytest.mark.asyncio
    async def test_run_service_client_exception(self):
        """Test run_service when client raises an exception."""
        self.mock_client.gateway_manager.run_service.side_effect = Exception(
            "Gateway communication error"
        )

        with pytest.raises(Exception, match="Gateway communication error"):
            await run_service(
                self.mock_context, name="service", cluster="cluster", input_params=None
            )

        # Verify context info was still called
        self.mock_context.debug.assert_called_once_with("inside run_service(...)")

    @pytest.mark.asyncio
    async def test_run_service_with_empty_output(self):
        """Test service run with empty stdout and stderr."""
        mock_data = {
            "result": {
                "stdout": "",
                "stderr": "",
                "return_code": 0,
                "start_time": "2025-01-22T10:00:00.000Z",
                "end_time": "2025-01-22T10:00:00.100Z",
                "elapsed_time": 0.1,
            }
        }
        self.mock_client.gateway_manager.run_service.return_value = mock_data

        result = await run_service(
            self.mock_context,
            name="silent-service",
            cluster="test-cluster",
            input_params=None,
        )

        assert isinstance(result, RunServiceResponse)
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.return_code == 0
        assert result.elapsed_time == 0.1

    @pytest.mark.asyncio
    async def test_run_service_with_unicode_output(self):
        """Test service run with Unicode characters in output."""
        unicode_data = {
            "status": "success",
            "messages": [
                "操作成功完成 ✅",
                "Процесс завершен успешно",
                "Opération réussie 🎉",
            ],
        }
        mock_data = {
            "result": {
                "stdout": json.dumps(unicode_data),
                "stderr": "Attention: mode de test activé ⚠️\nВнимание: тестовый режим",
                "return_code": 0,
                "start_time": "2025-01-22T10:00:00.000Z",
                "end_time": "2025-01-22T10:00:03.000Z",
                "elapsed_time": 3.0,
            }
        }
        self.mock_client.gateway_manager.run_service.return_value = mock_data

        result = await run_service(
            self.mock_context,
            name="unicode-service",
            cluster="international-cluster",
            input_params=None,
        )

        assert isinstance(result, RunServiceResponse)
        # stdout should be parsed as JSON
        assert isinstance(result.stdout, dict)
        assert result.stdout["status"] == "success"
        assert "操作成功完成 ✅" in result.stdout["messages"]
        assert "Процесс завершен успешно" in result.stdout["messages"]
        assert "Opération réussie 🎉" in result.stdout["messages"]
        assert "Attention: mode de test activé ⚠️" in result.stderr


class TestExportGatewayConfiguration(TestGatewayManagerTools):
    """Test cases for export_gateway_configuration function."""

    def test_export_gateway_configuration_function_exists(self):
        """Test that export_gateway_configuration function exists and is callable."""
        assert callable(export_gateway_configuration)

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_success(self):
        """Test successful export returns the expected wrapped model."""
        document = {
            "version": "1.0",
            "resources": [{"type": "service", "name": "svc-1"}],
        }
        self.mock_client.gateway_manager.export_configuration.return_value = document

        result = await export_gateway_configuration(
            self.mock_context, cluster_id="cluster_1"
        )

        self.mock_context.debug.assert_called_once_with(
            "inside export_gateway_configuration(...)"
        )
        self.mock_client.gateway_manager.export_configuration.assert_called_once_with(
            "cluster_1"
        )

        assert isinstance(result, ExportGatewayConfigurationResponse)
        assert result.root == document

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_client_error(self):
        """Test export_gateway_configuration when client raises an exception."""
        self.mock_client.gateway_manager.export_configuration.side_effect = Exception(
            "Gateway not connected"
        )

        with pytest.raises(Exception, match="Gateway not connected"):
            await export_gateway_configuration(
                self.mock_context, cluster_id="cluster_1"
            )

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_non_sensitive_no_elicit(self):
        """Non-sensitive export returns normally without elicitation."""
        document = {
            "decorators": [],
            "executable-objects": [],
            "mcp_servers": [],
            "registries": [],
            "repositories": [],
            "secret-providers": [],
            "services": [{"name": "svc-1"}],
        }
        self.mock_client.gateway_manager.export_configuration.return_value = document
        self.mock_context.session = MagicMock()
        self.mock_context.session.check_client_capability = MagicMock()
        self.mock_context.elicit = AsyncMock()

        result = await export_gateway_configuration(
            self.mock_context, cluster_id="cluster_1"
        )

        assert isinstance(result, ExportGatewayConfigurationResponse)
        assert result.root == document
        self.mock_context.elicit.assert_not_called()
        self.mock_context.session.check_client_capability.assert_not_called()

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_top_level_secrets_accept(self):
        """Sensitive top-level secrets + capable client + accept returns data."""
        document = {
            "secrets": [{"name": "sec1", "value": "enc-value"}],
            "users": [],
            "services": [],
        }
        self.mock_client.gateway_manager.export_configuration.return_value = document
        self.mock_context.session = MagicMock()
        self.mock_context.session.check_client_capability = MagicMock(return_value=True)
        self.mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(data=True)
        )

        result = await export_gateway_configuration(
            self.mock_context, cluster_id="cluster_1"
        )

        assert isinstance(result, ExportGatewayConfigurationResponse)
        assert result.root == document
        self.mock_context.elicit.assert_called_once()
        self.mock_context.session.check_client_capability.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_top_level_users_accept(self):
        """Sensitive top-level users (no secrets) + capable client + accept."""
        document = {
            "users": [{"name": "admin", "password": "hash"}],
            "secrets": [],
            "services": [],
        }
        self.mock_client.gateway_manager.export_configuration.return_value = document
        self.mock_context.session = MagicMock()
        self.mock_context.session.check_client_capability = MagicMock(return_value=True)
        self.mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(data=True)
        )

        result = await export_gateway_configuration(
            self.mock_context, cluster_id="cluster_1"
        )

        assert isinstance(result, ExportGatewayConfigurationResponse)
        assert result.root == document
        self.mock_context.elicit.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_nested_service_secrets_accept(self):
        """Nested per-service secrets (no top-level secrets/users) still triggers."""
        document = {
            "services": [
                {"name": "svc-1", "secrets": []},
                {"name": "svc-2", "secrets": [{"name": "sec1"}]},
            ],
        }
        self.mock_client.gateway_manager.export_configuration.return_value = document
        self.mock_context.session = MagicMock()
        self.mock_context.session.check_client_capability = MagicMock(return_value=True)
        self.mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(data=True)
        )

        result = await export_gateway_configuration(
            self.mock_context, cluster_id="cluster_1"
        )

        assert isinstance(result, ExportGatewayConfigurationResponse)
        assert result.root == document
        self.mock_context.elicit.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_declined_raises(self):
        """DeclinedElicitation raises AuthorizationException."""
        document = {"secrets": [{"name": "sec1"}]}
        self.mock_client.gateway_manager.export_configuration.return_value = document
        self.mock_context.session = MagicMock()
        self.mock_context.session.check_client_capability = MagicMock(return_value=True)
        self.mock_context.elicit = AsyncMock(return_value=DeclinedElicitation())

        with pytest.raises(AuthorizationException):
            await export_gateway_configuration(
                self.mock_context, cluster_id="cluster_1"
            )

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_cancelled_raises(self):
        """CancelledElicitation raises AuthorizationException."""
        document = {"secrets": [{"name": "sec1"}]}
        self.mock_client.gateway_manager.export_configuration.return_value = document
        self.mock_context.session = MagicMock()
        self.mock_context.session.check_client_capability = MagicMock(return_value=True)
        self.mock_context.elicit = AsyncMock(return_value=CancelledElicitation())

        with pytest.raises(AuthorizationException):
            await export_gateway_configuration(
                self.mock_context, cluster_id="cluster_1"
            )

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_accepted_false_raises(self):
        """AcceptedElicitation(data=False) raises AuthorizationException."""
        document = {"secrets": [{"name": "sec1"}]}
        self.mock_client.gateway_manager.export_configuration.return_value = document
        self.mock_context.session = MagicMock()
        self.mock_context.session.check_client_capability = MagicMock(return_value=True)
        self.mock_context.elicit = AsyncMock(
            return_value=AcceptedElicitation(data=False)
        )

        with pytest.raises(AuthorizationException):
            await export_gateway_configuration(
                self.mock_context, cluster_id="cluster_1"
            )

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_unrecognized_result_raises(self):
        """An unrecognized elicitation result raises AuthorizationException.

        This proves the fail-closed guarantee does not implicitly depend on
        ctx.elicit() only ever returning one of the known elicitation result
        types -- if it ever returned something else, the function must still
        raise rather than fall through the match and return None.
        """
        document = {"secrets": [{"name": "sec1"}]}
        self.mock_client.gateway_manager.export_configuration.return_value = document
        self.mock_context.session = MagicMock()
        self.mock_context.session.check_client_capability = MagicMock(return_value=True)
        self.mock_context.elicit = AsyncMock(return_value=object())

        with pytest.raises(AuthorizationException):
            await export_gateway_configuration(
                self.mock_context, cluster_id="cluster_1"
            )

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_incapable_client_raises(self):
        """Incapable client raises AuthorizationException without calling elicit."""
        document = {"secrets": [{"name": "sec1"}]}
        self.mock_client.gateway_manager.export_configuration.return_value = document
        self.mock_context.session = MagicMock()
        self.mock_context.session.check_client_capability = MagicMock(
            return_value=False
        )
        self.mock_context.elicit = AsyncMock()

        with pytest.raises(AuthorizationException):
            await export_gateway_configuration(
                self.mock_context, cluster_id="cluster_1"
            )

        self.mock_context.elicit.assert_not_called()

    @pytest.mark.asyncio
    async def test_export_gateway_configuration_private_key_name_not_sensitive(self):
        """A repositories entry with private-key-name alone does not trigger."""
        document = {
            "repositories": [
                {"name": "repo-1", "private-key-name": "my-ssh-key"},
            ],
            "services": [],
        }
        self.mock_client.gateway_manager.export_configuration.return_value = document
        self.mock_context.session = MagicMock()
        self.mock_context.session.check_client_capability = MagicMock()
        self.mock_context.elicit = AsyncMock()

        result = await export_gateway_configuration(
            self.mock_context, cluster_id="cluster_1"
        )

        assert isinstance(result, ExportGatewayConfigurationResponse)
        assert result.root == document
        self.mock_context.elicit.assert_not_called()
        self.mock_context.session.check_client_capability.assert_not_called()


class TestExportContainsSensitiveData:
    """Direct unit tests for the _export_contains_sensitive_data helper."""

    def test_empty_dict(self):
        """An empty document is not sensitive."""
        assert _export_contains_sensitive_data({}) is False

    def test_top_level_secrets_only(self):
        """Non-empty top-level secrets triggers detection."""
        document = {"secrets": [{"name": "sec1", "value": "enc"}]}
        assert _export_contains_sensitive_data(document) is True

    def test_top_level_users_only(self):
        """Non-empty top-level users triggers detection."""
        document = {"users": [{"name": "admin", "password": "hash"}]}
        assert _export_contains_sensitive_data(document) is True

    def test_nested_service_secrets_only(self):
        """A service entry with non-empty secrets triggers detection."""
        document = {
            "services": [
                {"name": "svc-1", "secrets": []},
                {"name": "svc-2", "secrets": [{"name": "sec1"}]},
            ]
        }
        assert _export_contains_sensitive_data(document) is True

    def test_private_key_name_alone_not_sensitive(self):
        """A repositories entry with private-key-name alone is not sensitive."""
        document = {
            "repositories": [{"name": "repo-1", "private-key-name": "my-ssh-key"}]
        }
        assert _export_contains_sensitive_data(document) is False

    def test_fully_clean_document(self):
        """A fully populated but non-sensitive document is not sensitive."""
        document = {
            "decorators": [{"name": "dec-1"}],
            "executable-objects": [{"name": "obj-1"}],
            "mcp_servers": [{"name": "mcp-1"}],
            "registries": [{"name": "reg-1"}],
            "repositories": [{"name": "repo-1", "private-key-name": "my-ssh-key"}],
            "secret-providers": [],
            "secrets": [],
            "services": [{"name": "svc-1", "secrets": []}],
            "users": [],
        }
        assert _export_contains_sensitive_data(document) is False


class TestImportGatewayConfiguration(TestGatewayManagerTools):
    """Test cases for import_gateway_configuration function."""

    def test_import_gateway_configuration_function_exists(self):
        """Test that import_gateway_configuration function exists and is callable."""
        assert callable(import_gateway_configuration)

    @pytest.mark.asyncio
    async def test_import_gateway_configuration_content_source_success(self):
        """Test valid content-source call succeeds."""
        expected_result = {
            "added": ["res_1"],
            "replaced": [],
            "skipped": [],
            "summary": {"added": 1, "replaced": 0, "skipped": 0},
        }
        self.mock_client.gateway_manager.import_configuration.return_value = (
            expected_result
        )

        result = await import_gateway_configuration(
            self.mock_context,
            cluster_id="cluster_1",
            content={"version": "1.0"},
            git_url=None,
            git_file=None,
            git_reference=None,
            git_username=None,
            git_password=None,
            git_private_key=None,
            force=False,
            validate=False,
            check=False,
        )

        self.mock_client.gateway_manager.import_configuration.assert_called_once_with(
            "cluster_1",
            source="content",
            content={"version": "1.0"},
            git=None,
            force=False,
            validate=False,
            check=False,
        )

        assert isinstance(result, ImportGatewayConfigurationResponse)
        assert result.added == ["res_1"]
        assert result.summary.added == 1

    @pytest.mark.asyncio
    async def test_import_gateway_configuration_git_source_all_fields(self):
        """Test valid git-source call succeeds with all git_* fields."""
        expected_result = {"added": [], "replaced": [], "skipped": []}
        self.mock_client.gateway_manager.import_configuration.return_value = (
            expected_result
        )

        result = await import_gateway_configuration(
            self.mock_context,
            cluster_id="cluster_1",
            content=None,
            git_url="https://example.com/repo.git",
            git_file="config.yml",
            git_reference="main",
            git_username="user",
            git_password="pass",
            git_private_key="/path/to/key",
            force=True,
            validate=False,
            check=False,
        )

        expected_git = {
            "url": "https://example.com/repo.git",
            "file": "config.yml",
            "reference": "main",
            "username": "user",
            "password": "pass",
            "privateKey": "/path/to/key",
        }
        self.mock_client.gateway_manager.import_configuration.assert_called_once_with(
            "cluster_1",
            source="git",
            content=None,
            git=expected_git,
            force=True,
            validate=False,
            check=False,
        )

        assert isinstance(result, ImportGatewayConfigurationResponse)

    @pytest.mark.asyncio
    async def test_import_gateway_configuration_git_source_minimal(self):
        """Test valid git-source call succeeds with only git_url and git_file."""
        expected_result = {"added": [], "replaced": [], "skipped": []}
        self.mock_client.gateway_manager.import_configuration.return_value = (
            expected_result
        )

        await import_gateway_configuration(
            self.mock_context,
            cluster_id="cluster_1",
            content=None,
            git_url="https://example.com/repo.git",
            git_file="config.yml",
            git_reference=None,
            git_username=None,
            git_password=None,
            git_private_key=None,
            force=False,
            validate=False,
            check=False,
        )

        expected_git = {
            "url": "https://example.com/repo.git",
            "file": "config.yml",
        }
        self.mock_client.gateway_manager.import_configuration.assert_called_once_with(
            "cluster_1",
            source="git",
            content=None,
            git=expected_git,
            force=False,
            validate=False,
            check=False,
        )

    @pytest.mark.asyncio
    async def test_import_gateway_configuration_validate_and_check_raises(self):
        """Test validate=True and check=True together raises ValidationException."""
        with pytest.raises(ValidationException):
            await import_gateway_configuration(
                self.mock_context,
                cluster_id="cluster_1",
                content={"version": "1.0"},
                git_url=None,
                git_file=None,
                git_reference=None,
                git_username=None,
                git_password=None,
                git_private_key=None,
                force=False,
                validate=True,
                check=True,
            )

        self.mock_client.gateway_manager.import_configuration.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_gateway_configuration_content_and_git_raises(self):
        """Test content set AND git_url set together raises ValidationException."""
        with pytest.raises(ValidationException):
            await import_gateway_configuration(
                self.mock_context,
                cluster_id="cluster_1",
                content={"version": "1.0"},
                git_url="https://example.com/repo.git",
                git_file=None,
                git_reference=None,
                git_username=None,
                git_password=None,
                git_private_key=None,
                force=False,
                validate=False,
                check=False,
            )

        self.mock_client.gateway_manager.import_configuration.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_gateway_configuration_no_source_raises(self):
        """Test neither content nor git_url set raises ValidationException."""
        with pytest.raises(ValidationException):
            await import_gateway_configuration(
                self.mock_context,
                cluster_id="cluster_1",
                content=None,
                git_url=None,
                git_file=None,
                git_reference=None,
                git_username=None,
                git_password=None,
                git_private_key=None,
                force=False,
                validate=False,
                check=False,
            )

        self.mock_client.gateway_manager.import_configuration.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_gateway_configuration_git_url_without_git_file_raises(self):
        """Test git_url set without git_file raises ValidationException."""
        with pytest.raises(ValidationException):
            await import_gateway_configuration(
                self.mock_context,
                cluster_id="cluster_1",
                content=None,
                git_url="https://example.com/repo.git",
                git_file=None,
                git_reference=None,
                git_username=None,
                git_password=None,
                git_private_key=None,
                force=False,
                validate=False,
                check=False,
            )

        self.mock_client.gateway_manager.import_configuration.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_gateway_configuration_git_file_without_git_url_raises(self):
        """Test git_file set without git_url raises ValidationException."""
        with pytest.raises(ValidationException):
            await import_gateway_configuration(
                self.mock_context,
                cluster_id="cluster_1",
                content=None,
                git_url=None,
                git_file="config.yml",
                git_reference=None,
                git_username=None,
                git_password=None,
                git_private_key=None,
                force=False,
                validate=False,
                check=False,
            )

        self.mock_client.gateway_manager.import_configuration.assert_not_called()


class TestGatewayManagerToolsModule:
    """Test cases for module-level functionality."""

    def test_module_tags_attribute(self):
        """Test that the module has correct tags attribute."""
        from itential_mcp.tools import gateway_manager

        assert hasattr(gateway_manager, "__tags__")
        assert gateway_manager.__tags__ == ("gateway_manager",)

    def test_all_functions_are_async(self):
        """Test that all tool functions are async."""
        import inspect
        from itential_mcp.tools import gateway_manager

        functions_to_test = [
            gateway_manager.get_services,
            gateway_manager.get_gateways,
            gateway_manager.run_service,
        ]

        for func in functions_to_test:
            assert inspect.iscoroutinefunction(func), f"{func.__name__} should be async"

    def test_function_signatures(self):
        """Test that all functions have correct signatures."""
        import inspect
        from itential_mcp.tools import gateway_manager

        # Test get_services signature
        sig = inspect.signature(gateway_manager.get_services)
        params = list(sig.parameters.keys())
        assert params == ["ctx"]

        # Test get_gateways signature
        sig = inspect.signature(gateway_manager.get_gateways)
        params = list(sig.parameters.keys())
        assert params == ["ctx"]

        # Test run_service signature
        sig = inspect.signature(gateway_manager.run_service)
        params = list(sig.parameters.keys())
        assert params == ["ctx", "name", "cluster", "input_params"]

    def test_function_docstrings_exist(self):
        """Test that all functions have proper docstrings."""
        from itential_mcp.tools import gateway_manager

        functions_to_test = [
            gateway_manager.get_services,
            gateway_manager.get_gateways,
            gateway_manager.run_service,
        ]

        for func in functions_to_test:
            assert func.__doc__ is not None, f"{func.__name__} should have docstring"
            assert len(func.__doc__.strip()) > 0, (
                f"{func.__name__} docstring should not be empty"
            )

            # Check for required docstring sections
            docstring = func.__doc__
            assert "Args:" in docstring, (
                f"{func.__name__} docstring should have Args section"
            )
            assert "Returns:" in docstring, (
                f"{func.__name__} docstring should have Returns section"
            )
            assert "Raises:" in docstring, (
                f"{func.__name__} docstring should have Raises section"
            )

    def test_function_return_type_annotations(self):
        """Test that all functions have proper return type annotations."""
        import inspect
        from itential_mcp.tools import gateway_manager
        from itential_mcp.models.gateway_manager import (
            GetServicesResponse,
            GetGatewaysResponse,
            RunServiceResponse,
        )

        # Test get_services return annotation
        sig = inspect.signature(gateway_manager.get_services)
        assert sig.return_annotation == GetServicesResponse

        # Test get_gateways return annotation
        sig = inspect.signature(gateway_manager.get_gateways)
        assert sig.return_annotation == GetGatewaysResponse

        # Test run_service return annotation
        sig = inspect.signature(gateway_manager.run_service)
        assert sig.return_annotation == RunServiceResponse


class TestGatewayManagerErrorHandling:
    """Test cases for error handling scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_context = AsyncMock(spec=Context)
        self.mock_context.debug = AsyncMock()
        self.mock_client = MagicMock()
        self.mock_context.request_context.lifespan_context.get.return_value = (
            self.mock_client
        )

    @pytest.mark.asyncio
    async def test_get_services_missing_service_metadata(self):
        """Test get_services handling malformed service data."""
        mock_data = [
            {
                # Missing service_metadata key
                "metadata": {"name": "broken-service"}
            }
        ]

        self.mock_client.gateway_manager = MagicMock()
        self.mock_client.gateway_manager.get_services = AsyncMock(
            return_value=mock_data
        )

        with pytest.raises(KeyError):
            await get_services(self.mock_context)

    @pytest.mark.asyncio
    async def test_get_gateways_missing_gateway_fields(self):
        """Test get_gateways handling malformed gateway data with missing fields."""
        mock_data = {
            "results": [
                {
                    "gateway_name": "incomplete-gateway",
                    "connection_status": "connected",
                    # Missing cluster_id, description, enabled - should use defaults
                }
            ]
        }

        self.mock_client.gateway_manager = MagicMock()
        self.mock_client.gateway_manager.get_gateways = AsyncMock(
            return_value=mock_data
        )

        # Should not raise an error, but handle missing fields gracefully with defaults
        result = await get_gateways(self.mock_context)

        # Verify it returns a result with default values for missing fields
        assert isinstance(result, GetGatewaysResponse)
        assert len(result.root) == 1
        assert result.root[0].name == "incomplete-gateway"
        assert result.root[0].cluster == ""  # Default value
        assert result.root[0].description == ""  # Default value
        assert result.root[0].enabled is False  # Default value

    @pytest.mark.asyncio
    async def test_run_service_missing_result_fields(self):
        """Test run_service handling malformed result data."""
        mock_data = {
            "result": {
                "stdout": "output",
                # Missing stderr, return_code, start_time, end_time, elapsed_time
            }
        }

        self.mock_client.gateway_manager = MagicMock()
        self.mock_client.gateway_manager.run_service = AsyncMock(return_value=mock_data)

        with pytest.raises(Exception):  # Could be KeyError or ValidationError
            await run_service(self.mock_context, "service", "cluster", None)
