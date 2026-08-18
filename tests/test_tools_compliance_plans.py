# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from unittest.mock import AsyncMock, MagicMock

from itential_mcp.tools.compliance_plans import (
    get_compliance_plans,
    run_compliance_plan,
)
from itential_mcp.models.compliance_plans import (
    GetCompliancePlansResponse,
    RunCompliancePlanResponse,
)
from fastmcp import Context


class TestGetCompliancePlansTool:
    """Regression tests for Bug 4 — get_compliance_plans must await the service call.

    Previously, client.configuration_manager.get_compliance_plans() was called
    without await, causing the coroutine object itself to be passed to the Pydantic
    model, producing: ValidationError "Input should be a valid list ... coroutine".
    """

    def setup_method(self):
        """Set up shared mock fixtures."""
        self.mock_context = AsyncMock(spec=Context)
        self.mock_context.debug = AsyncMock()

        self.mock_client = MagicMock()
        self.mock_cm_service = MagicMock()
        self.mock_cm_service.get_compliance_plans = AsyncMock()

        self.mock_client.configuration_manager = self.mock_cm_service
        self.mock_context.request_context.lifespan_context.get.return_value = (
            self.mock_client
        )

    @pytest.mark.asyncio
    async def test_get_compliance_plans_awaits_service_call(self):
        """get_compliance_plans must await the configuration_manager service call.

        The mock is an AsyncMock — if the tool does NOT await it, the coroutine
        object propagates to Pydantic and raises ValidationError.  If it DOES await,
        the mock returns the configured list and the response model is valid.
        """
        self.mock_cm_service.get_compliance_plans.return_value = [
            {
                "id": "plan-1",
                "name": "Security Baseline",
                "description": "Checks security config",
                "throttle": 5,
            },
            {
                "id": "plan-2",
                "name": "QoS Compliance",
                "description": "Validates QoS settings",
                "throttle": 10,
            },
        ]

        result = await get_compliance_plans(self.mock_context)

        self.mock_cm_service.get_compliance_plans.assert_awaited_once()
        assert isinstance(result, GetCompliancePlansResponse)
        assert len(result.plans) == 2
        assert result.plans[0].name == "Security Baseline"
        assert result.plans[1].name == "QoS Compliance"

    @pytest.mark.asyncio
    async def test_get_compliance_plans_empty_list(self):
        """get_compliance_plans must handle an empty plans list gracefully."""
        self.mock_cm_service.get_compliance_plans.return_value = []

        result = await get_compliance_plans(self.mock_context)

        self.mock_cm_service.get_compliance_plans.assert_awaited_once()
        assert isinstance(result, GetCompliancePlansResponse)
        assert result.plans == []

    @pytest.mark.asyncio
    async def test_get_compliance_plans_logs_entry(self):
        """get_compliance_plans must log entry via ctx.debug."""
        self.mock_cm_service.get_compliance_plans.return_value = []

        await get_compliance_plans(self.mock_context)

        self.mock_context.debug.assert_called_once_with(
            "inside get_compliance_plans(...)"
        )


class TestRunCompliancePlanTool:
    """Regression tests for Bug 4b — run_compliance_plan must also await its service call.

    Discovered via code review: the same missing-await pattern exists at
    tools/compliance_plans.py:64 for run_compliance_plan.
    """

    def setup_method(self):
        """Set up shared mock fixtures."""
        self.mock_context = AsyncMock(spec=Context)
        self.mock_context.debug = AsyncMock()

        self.mock_client = MagicMock()
        self.mock_cm_service = MagicMock()
        self.mock_cm_service.run_compliance_plan = AsyncMock()

        self.mock_client.configuration_manager = self.mock_cm_service
        self.mock_context.request_context.lifespan_context.get.return_value = (
            self.mock_client
        )

    @pytest.mark.asyncio
    async def test_run_compliance_plan_awaits_service_call(self):
        """run_compliance_plan must await the configuration_manager service call."""
        self.mock_cm_service.run_compliance_plan.return_value = {
            "id": "instance-123",
            "name": "Security Baseline",
            "description": "Checks security config",
            "jobStatus": "running",
            "batchId": "67ead32d5f12757d048a48df",
        }

        result = await run_compliance_plan(self.mock_context, name="Security Baseline")

        self.mock_cm_service.run_compliance_plan.assert_awaited_once_with(
            name="Security Baseline"
        )
        assert isinstance(result, RunCompliancePlanResponse)
        assert result.instance.id == "instance-123"
        assert result.instance.jobStatus == "running"
        assert result.instance.batchId == "67ead32d5f12757d048a48df"

    @pytest.mark.asyncio
    async def test_run_compliance_plan_passes_name(self):
        """run_compliance_plan must pass the plan name to the service."""
        self.mock_cm_service.run_compliance_plan.return_value = {
            "id": "inst-456",
            "name": "QoS Compliance",
            "description": "Validates QoS",
            "jobStatus": "complete",
        }

        await run_compliance_plan(self.mock_context, name="QoS Compliance")

        call_kwargs = self.mock_cm_service.run_compliance_plan.call_args
        assert call_kwargs.kwargs.get("name") == "QoS Compliance"

    @pytest.mark.asyncio
    async def test_run_compliance_plan_surfaces_batch_id(self):
        """run_compliance_plan must surface batchId from the raw service payload.

        This is the anti-drop regression test: it returns a full raw instance
        dict (all real fields the platform sends, including extras the tool
        does not model) and asserts batchId survives into the response while
        unmodeled extra keys are silently ignored.
        """
        self.mock_cm_service.run_compliance_plan.return_value = {
            "id": "instance-999",
            "planId": "plan-999",
            "jobId": "job-999",
            "name": "Full Payload Plan",
            "description": "Exercises the full raw instance payload",
            "jobStatus": "running",
            "started": "2026-08-18T00:00:00Z",
            "throttle": 5,
            "nodes": ["node1", "node2"],
            "batchId": "67ead32d5f12757d048a48df",
        }

        result = await run_compliance_plan(self.mock_context, name="Full Payload Plan")

        assert isinstance(result, RunCompliancePlanResponse)
        assert result.instance.batchId == "67ead32d5f12757d048a48df"
