# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from unittest.mock import AsyncMock, MagicMock

from itential_mcp.tools.applications import get_applications, start_application
from itential_mcp.models.applications import (
    GetApplicationsResponse,
    StartApplicationResponse,
)
from fastmcp import Context


class TestStartApplicationTool:
    """Regression tests for Bug 06 — start_application must await the service call.

    Previously, client.applications.start_application() was called without await,
    causing a TypeError: 'coroutine' object is not subscriptable when the tool
    attempted data["id"] on the unawaited coroutine.

    The sibling tools stop_application (line 129) and restart_application (line 168)
    in the same file both correctly await their service calls. This test class ensures
    start_application is consistent with that pattern.
    """

    def setup_method(self):
        """Set up shared mock fixtures."""
        self.mock_context = AsyncMock(spec=Context)
        self.mock_context.debug = AsyncMock()

        self.mock_client = MagicMock()
        self.mock_app_service = MagicMock()
        self.mock_app_service.start_application = AsyncMock()

        self.mock_client.applications = self.mock_app_service
        self.mock_context.request_context.lifespan_context.get.return_value = (
            self.mock_client
        )

    @pytest.mark.asyncio
    async def test_start_application_awaits_service_call(self):
        """start_application must await the applications service call.

        The mock is an AsyncMock — if the tool does NOT await it, the coroutine
        object propagates and data["id"] raises TypeError. If it DOES await,
        the mock returns the configured dict and the response model is valid.
        """
        self.mock_app_service.start_application.return_value = {
            "id": "WorkFlowEngine",
            "state": "RUNNING",
        }

        result = await start_application(
            self.mock_context, name="WorkFlowEngine", timeout=10
        )

        self.mock_app_service.start_application.assert_awaited_once()
        assert isinstance(result, StartApplicationResponse)
        assert result.name == "WorkFlowEngine"
        assert result.state == "RUNNING"

    @pytest.mark.asyncio
    async def test_start_application_passes_name_and_timeout(self):
        """start_application must pass name and timeout positionally to the service."""
        self.mock_app_service.start_application.return_value = {
            "id": "AutomationStudio",
            "state": "RUNNING",
        }

        await start_application(self.mock_context, name="AutomationStudio", timeout=30)

        self.mock_app_service.start_application.assert_awaited_once_with(
            "AutomationStudio", 30
        )

    @pytest.mark.asyncio
    async def test_start_application_returns_correct_response_type(self):
        """start_application must return a StartApplicationResponse instance."""
        self.mock_app_service.start_application.return_value = {
            "id": "FormBuilder",
            "state": "RUNNING",
        }

        result = await start_application(
            self.mock_context, name="FormBuilder", timeout=10
        )

        assert isinstance(result, StartApplicationResponse)

    @pytest.mark.asyncio
    async def test_start_application_maps_id_to_name(self):
        """start_application must map the platform's id field to the response name field."""
        self.mock_app_service.start_application.return_value = {
            "id": "Search",
            "state": "RUNNING",
        }

        result = await start_application(self.mock_context, name="Search", timeout=10)

        assert result.name == "Search"

    @pytest.mark.asyncio
    async def test_start_application_logs_entry(self):
        """start_application must log entry via ctx.debug."""
        self.mock_app_service.start_application.return_value = {
            "id": "Tags",
            "state": "RUNNING",
        }

        await start_application(self.mock_context, name="Tags", timeout=10)

        self.mock_context.debug.assert_called_once_with("inside start_application(...)")


class TestGetApplicationsTool:
    """Regression tests for get_applications with null/missing fields.

    GetApplicationsElement previously declared description, package, and
    version as required non-nullable strings, even though get_applications
    sources all three via .get() on the raw platform response -- which can
    already yield None. At least one real platform application
    (ModelRegistryService) returns description: null, causing
    get_applications to fail outright with a Pydantic validation error for
    the entire result set on a single bad record. These tests confirm the
    widened Optional fields tolerate null and missing values, mirroring the
    identical fix already applied to health.py's ApplicationInfo model.
    """

    def setup_method(self):
        """Set up shared mock fixtures."""
        self.mock_context = AsyncMock(spec=Context)
        self.mock_context.debug = AsyncMock()

        self.mock_client = MagicMock()
        self.mock_client.get = AsyncMock()
        self.mock_context.request_context.lifespan_context.get.return_value = (
            self.mock_client
        )

    @pytest.mark.asyncio
    async def test_get_applications_tolerates_null_description(self):
        """get_applications must not raise when one record has a null description.

        Replicates the live failure observed with ModelRegistryService,
        which returns description: null alongside otherwise normal
        application records.
        """
        res = MagicMock()
        res.json = MagicMock(
            return_value={
                "results": [
                    {
                        "id": "ModelRegistryService",
                        "package_id": "@itential/model-registry-service",
                        "version": "1.0.0",
                        "description": None,
                        "state": "RUNNING",
                    },
                    {
                        "id": "WorkFlowEngine",
                        "package_id": "@itential/workflow-engine",
                        "version": "2.0.0",
                        "description": "Executes workflows",
                        "state": "RUNNING",
                    },
                ]
            }
        )
        self.mock_client.get = AsyncMock(return_value=res)

        result = await get_applications(self.mock_context)

        assert isinstance(result, GetApplicationsResponse)
        assert len(result.root) == 2
        assert result.root[0].name == "ModelRegistryService"
        assert result.root[0].description is None
        assert result.root[1].description == "Executes workflows"

    @pytest.mark.asyncio
    async def test_get_applications_tolerates_missing_description_key(self):
        """get_applications must not raise when description key is absent entirely.

        The .get() call returns None whether the key is null or missing,
        but both shapes are worth covering explicitly.
        """
        res = MagicMock()
        res.json = MagicMock(
            return_value={
                "results": [
                    {
                        "id": "SomeApp",
                        "package_id": "@itential/some-app",
                        "version": "1.0.0",
                        "state": "RUNNING",
                    },
                ]
            }
        )
        self.mock_client.get = AsyncMock(return_value=res)

        result = await get_applications(self.mock_context)

        assert isinstance(result, GetApplicationsResponse)
        assert len(result.root) == 1
        assert result.root[0].description is None

    @pytest.mark.asyncio
    async def test_get_applications_tolerates_null_package_and_version(self):
        """get_applications must not raise when package or version are null."""
        res = MagicMock()
        res.json = MagicMock(
            return_value={
                "results": [
                    {
                        "id": "NullPackageApp",
                        "package_id": None,
                        "version": "1.0.0",
                        "description": "Has null package",
                        "state": "RUNNING",
                    },
                    {
                        "id": "NullVersionApp",
                        "package_id": "@itential/null-version-app",
                        "version": None,
                        "description": "Has null version",
                        "state": "RUNNING",
                    },
                ]
            }
        )
        self.mock_client.get = AsyncMock(return_value=res)

        result = await get_applications(self.mock_context)

        assert isinstance(result, GetApplicationsResponse)
        assert len(result.root) == 2
        assert result.root[0].package is None
        assert result.root[0].version == "1.0.0"
        assert result.root[1].package == "@itential/null-version-app"
        assert result.root[1].version is None

    @pytest.mark.asyncio
    async def test_get_applications_happy_path_maps_all_fields(self):
        """get_applications must correctly map all fields when fully populated."""
        res = MagicMock()
        res.json = MagicMock(
            return_value={
                "results": [
                    {
                        "id": "AutomationStudio",
                        "package_id": "@itential/automation-studio",
                        "version": "5.2.1",
                        "description": "Design and manage automations",
                        "state": "RUNNING",
                    },
                ]
            }
        )
        self.mock_client.get = AsyncMock(return_value=res)

        result = await get_applications(self.mock_context)

        assert isinstance(result, GetApplicationsResponse)
        assert len(result.root) == 1
        element = result.root[0]
        assert element.name == "AutomationStudio"
        assert element.package == "@itential/automation-studio"
        assert element.version == "5.2.1"
        assert element.description == "Design and manage automations"
        assert element.state == "RUNNING"

    @pytest.mark.asyncio
    async def test_get_applications_logs_entry(self):
        """get_applications must log entry via ctx.debug."""
        res = MagicMock()
        res.json = MagicMock(return_value={"results": []})
        self.mock_client.get = AsyncMock(return_value=res)

        await get_applications(self.mock_context)

        self.mock_context.debug.assert_called_once_with("inside get_applications(...)")
