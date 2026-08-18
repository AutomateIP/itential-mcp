# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Annotated

from pydantic import Field

from fastmcp import Context

from itential_mcp.models import compliance_reports as models
from itential_mcp.utilities.tool import annotate


__tags__ = ("configuration_manager",)


@annotate(
    read_only=True,
    idempotent=True,
    open_world=False,
    title="Describe Compliance Report",
)
async def describe_compliance_report(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
    report_id: Annotated[str, Field(description="The ID of the report to describe")],
) -> models.DescribeComplianceReportResponse:
    """
    Retrieve detailed compliance report results from Itential Platform.

    Compliance reports contain the results of executing compliance plans against
    network devices, showing configuration validation outcomes, rule violations,
    and compliance status for each checked device.

    Args:
        ctx (Context): The FastMCP Context object
        report_id (str): Unique identifier of the compliance report to retrieve

    Returns:
        models.DescribeComplianceReportResponse: Compliance report details containing validation results, device
            compliance status, rule violations, and configuration analysis from
            running compliance checks against network infrastructure

    Raises:
        Exception: If there is an error retrieving the compliance report or the report ID is not found
    """
    await ctx.debug("inside describe_compliance_report(...)")
    client = ctx.request_context.lifespan_context.get("client")
    res = await client.configuration_manager.describe_compliance_report(report_id)
    return models.DescribeComplianceReportResponse(result=res)


@annotate(
    read_only=True,
    idempotent=True,
    open_world=False,
    title="Get Compliance Reports By Batch",
)
async def get_compliance_reports_by_batch(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
    batch_id: Annotated[
        str,
        Field(
            description=(
                "The batch ID from a compliance plan run "
                "(CompliancePlanInstance.batchId) to fetch reports for"
            )
        ),
    ],
) -> models.GetComplianceReportsByBatchResponse:
    """
    Retrieve compliance reports produced by a specific compliance plan batch run.

    Compliance reports are generated per-device when a compliance plan is
    executed. All reports produced by a single plan run share the same batch
    identifier. This tool closes the chain from running a plan to inspecting
    its results: run_compliance_plan returns instance.batchId, which is
    passed here to list per-device report summaries, and each report's id
    can then be passed to describe_compliance_report for full detail.

    Args:
        ctx (Context): The FastMCP Context object
        batch_id (str): The batch ID from a compliance plan run
            (CompliancePlanInstance.batchId) to fetch reports for

    Returns:
        models.GetComplianceReportsByBatchResponse: Response containing the
            list of compliance report brief objects produced by the batch run

    Raises:
        Exception: If there is an error retrieving the compliance reports from the platform
    """
    await ctx.debug("inside get_compliance_reports_by_batch(...)")
    client = ctx.request_context.lifespan_context.get("client")
    res = await client.configuration_manager.get_compliance_reports_by_batch(batch_id)
    return models.GetComplianceReportsByBatchResponse(reports=res)
